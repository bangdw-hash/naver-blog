# -*- coding: utf-8 -*-
"""
sync_service.py - 크로스 디바이스 동기화 (Supabase ↔ SQLite)
자동: 5분마다 백그라운드 스레드 / 수동: /api/sync 엔드포인트
"""
import os, json, threading, time, sqlite3
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

STATUS_FILE = Path(os.path.dirname(__file__)) / ".." / "data" / "sync_status.json"
_sync_lock  = threading.Lock()
_listeners  = []  # SSE 리스너 목록

def _load_status() -> dict:
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
        except: pass
    return {"last_sync": None, "pulled": 0, "pushed": 0, "errors": []}

def _save_status(status: dict):
    STATUS_FILE.parent.mkdir(exist_ok=True)
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

def get_sync_status() -> dict:
    return _load_status()

def _get_supabase():
    url = os.getenv("SUPABASE_URL","")
    key = os.getenv("SUPABASE_KEY","")
    if not url or not key: return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except: return None

# ── Supabase → SQLite (Pull) ─────────────────────────────────
def pull_from_supabase(callback=None) -> dict:
    """Supabase의 최신 데이터를 SQLite로 내려받기"""
    sb = _get_supabase()
    if not sb:
        return {"error": "Supabase 연결 실패"}

    pulled = 0
    errors = []

    # ── 블로그 게시물 동기화 ──
    try:
        from services.database import DB_PATH as BLOG_DB_PATH
        rows = sb.table("posts").select("*").order("created_at", desc=True).limit(500).execute()
        if rows.data:
            conn = sqlite3.connect(str(BLOG_DB_PATH))
            for row in rows.data:
                tags   = row.get("tags", [])
                images = row.get("images", [])
                if isinstance(tags,   list): tags   = json.dumps(tags,   ensure_ascii=False)
                if isinstance(images, list): images = json.dumps(images, ensure_ascii=False)
                conn.execute("""
                INSERT OR REPLACE INTO posts
                  (id,title,content,tags,main_keyword,tone,raw_input,concept,
                   naver_url,status,images,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    row.get("id",""), row.get("title",""), row.get("content",""),
                    tags, row.get("main_keyword",""), row.get("tone",""),
                    row.get("raw_input",""), row.get("concept",""),
                    row.get("naver_url",""), row.get("status","draft"),
                    images, row.get("created_at","")
                ))
                pulled += 1
            conn.commit(); conn.close()
            if callback: callback(f"블로그 글 {len(rows.data)}개 동기화")
    except Exception as e:
        errors.append(f"posts pull: {e}")

    # ── 맛집 게시물 동기화 ──
    try:
        from services.food_db import DB_PATH as FOOD_DB_PATH
        from services.food_db import init_food_db
        init_food_db()
        rows = sb.table("food_posts").select("*").order("created_at", desc=True).limit(500).execute()
        if rows.data:
            conn = sqlite3.connect(str(FOOD_DB_PATH))
            for row in rows.data:
                photos = row.get("photos", [])
                tags   = row.get("tags",   [])
                if isinstance(photos, list): photos = json.dumps(photos, ensure_ascii=False)
                if isinstance(tags,   list): tags   = json.dumps(tags,   ensure_ascii=False)
                conn.execute("""
                INSERT OR REPLACE INTO food_posts
                  (id,place_name,place_addr,visit_date,rating_taste,rating_mood,
                   price_range,revisit,party_size,memo,photos,title,content,tags,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    row.get("id",""), row.get("place_name",""), row.get("place_addr",""),
                    row.get("visit_date",""), row.get("rating_taste",3), row.get("rating_mood",3),
                    row.get("price_range",""), row.get("revisit",""), row.get("party_size",""),
                    row.get("memo",""), photos, row.get("title",""),
                    row.get("content",""), tags, row.get("status","draft"), row.get("created_at","")
                ))
                pulled += len(rows.data)
            conn.commit(); conn.close()
            if callback: callback(f"맛집 기록 {len(rows.data)}개 동기화")
    except Exception as e:
        errors.append(f"food_posts pull: {e}")

    # ── 블로그 로직 동기화 ──
    try:
        logic_rows = sb.table("blog_logic").select("*").order("updated_at", desc=True).limit(1).execute()
        if logic_rows.data:
            from services.blog_logic import LOGIC_PATH
            with open(LOGIC_PATH, "w", encoding="utf-8") as f:
                json.dump(logic_rows.data[0], f, ensure_ascii=False, indent=2)
            if callback: callback("블로그 로직 동기화 완료")
    except Exception as e:
        errors.append(f"blog_logic pull: {e}")

    return {"pulled": pulled, "errors": errors}

# ── SQLite → Supabase (Push) ─────────────────────────────────
def push_to_supabase(callback=None) -> dict:
    """로컬 SQLite 데이터를 Supabase로 올리기"""
    sb = _get_supabase()
    if not sb:
        return {"error": "Supabase 연결 실패"}

    pushed = 0
    errors = []

    try:
        from services.database import DB_PATH as BLOG_DB_PATH
        conn = sqlite3.connect(str(BLOG_DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT 200").fetchall()
        conn.close()
        for row in rows:
            d = dict(row)
            for k in ("tags","images","youtube_links"):
                try: d[k] = json.loads(d.get(k) or "[]")
                except: d[k] = []
            sb.table("posts").upsert(d).execute()
            pushed += 1
        if callback: callback(f"블로그 글 {pushed}개 업로드")
    except Exception as e:
        errors.append(f"posts push: {e}")

    return {"pushed": pushed, "errors": errors}

# ── 전체 동기화 ───────────────────────────────────────────────
def full_sync(direction: str = "pull", callback=None) -> dict:
    """direction: 'pull' | 'push' | 'both'"""
    with _sync_lock:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result = {"last_sync": now, "pulled": 0, "pushed": 0, "errors": []}

        if direction in ("pull", "both"):
            if callback: callback("⬇ Supabase → 로컬 동기화 중...")
            r = pull_from_supabase(callback)
            result["pulled"]  = r.get("pulled",  0)
            result["errors"] += r.get("errors", [])

        if direction in ("push", "both"):
            if callback: callback("⬆ 로컬 → Supabase 동기화 중...")
            r = push_to_supabase(callback)
            result["pushed"]  = r.get("pushed",  0)
            result["errors"] += r.get("errors", [])

        _save_status(result)
        if callback: callback(f"✓ 동기화 완료 (가져옴:{result['pulled']} 올림:{result['pushed']})")
        _notify_listeners(result)
        return result

def _notify_listeners(data: dict):
    for q in list(_listeners):
        try: q.put(data)
        except: pass

# ── 자동 동기화 백그라운드 스레드 ─────────────────────────────
_auto_sync_running = False

def start_auto_sync(interval_sec: int = 300):
    """앱 시작 시 한 번 호출 — 5분마다 자동 pull"""
    global _auto_sync_running
    if _auto_sync_running:
        return
    _auto_sync_running = True

    def _loop():
        while _auto_sync_running:
            try:
                full_sync("pull")
            except: pass
            time.sleep(interval_sec)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()

def stop_auto_sync():
    global _auto_sync_running
    _auto_sync_running = False

def register_sse_listener(q):
    _listeners.append(q)

def unregister_sse_listener(q):
    try: _listeners.remove(q)
    except: pass
