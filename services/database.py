# -*- coding: utf-8 -*-
"""
database.py - 게시글 이력 관리
Supabase(웹) + SQLite(로컬 백업) 듀얼 저장
"""
import os, json, sqlite3, uuid
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

DB_PATH = Path(__file__).parent.parent / "data" / "history.db"
DB_PATH.parent.mkdir(exist_ok=True)

# ── SQLite 초기화 ─────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id          TEXT PRIMARY KEY,
        title       TEXT,
        content     TEXT,
        tags        TEXT,
        main_keyword TEXT,
        tone        TEXT,
        raw_input   TEXT,
        concept     TEXT,
        images      TEXT,
        youtube_links TEXT,
        status      TEXT DEFAULT 'draft',
        naver_url   TEXT,
        created_at  TEXT,
        updated_at  TEXT
    )""")
    conn.commit(); conn.close()

init_db()

# ── Supabase 연결 (선택적) ────────────────────────────────
def get_supabase():
    url = os.getenv("SUPABASE_URL","")
    key = os.getenv("SUPABASE_KEY","")
    if url and key and "여기에입력" not in url:
        try:
            from supabase import create_client
            return create_client(url, key)
        except Exception:
            pass
    return None

# ── CRUD ─────────────────────────────────────────────────
def save_post(data: dict) -> str:
    """게시글 저장 (신규) → id 반환"""
    post_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    row = {
        "id":           post_id,
        "title":        data.get("title",""),
        "content":      data.get("content",""),
        "tags":         json.dumps(data.get("tags",[]), ensure_ascii=False),
        "main_keyword": data.get("main_keyword",""),
        "tone":         data.get("tone","친근하게"),
        "raw_input":    data.get("raw_input","")[:2000],
        "concept":      data.get("concept",""),
        "images":       json.dumps(data.get("images",[]), ensure_ascii=False),
        "youtube_links":json.dumps(data.get("youtube_links",[]), ensure_ascii=False),
        "status":       data.get("status","draft"),
        "naver_url":    data.get("naver_url",""),
        "created_at":   now,
        "updated_at":   now,
    }
    # SQLite 저장
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""INSERT INTO posts VALUES
        (:id,:title,:content,:tags,:main_keyword,:tone,:raw_input,:concept,
         :images,:youtube_links,:status,:naver_url,:created_at,:updated_at)""", row)
    conn.commit(); conn.close()
    # Supabase 동기화
    sb = get_supabase()
    if sb:
        try: sb.table("posts").insert(row).execute()
        except Exception: pass
    return post_id

def update_post(post_id: str, data: dict):
    """게시글 업데이트"""
    now = datetime.now().isoformat()
    fields = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list,dict)) else v)
              for k,v in data.items() if k != "id"}
    fields["updated_at"] = now
    set_clause = ", ".join([f"{k}=?" for k in fields])
    vals = list(fields.values()) + [post_id]
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(f"UPDATE posts SET {set_clause} WHERE id=?", vals)
    conn.commit(); conn.close()
    sb = get_supabase()
    if sb:
        try: sb.table("posts").update(fields).eq("id", post_id).execute()
        except Exception: pass

def get_post(post_id: str) -> dict:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
    conn.close()
    if not row: return {}
    d = dict(row)
    for key in ["tags","images","youtube_links"]:
        try: d[key] = json.loads(d[key] or "[]")
        except: d[key] = []
    return d

def list_posts(limit=50, offset=0) -> list:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id,title,main_keyword,tone,status,created_at,naver_url FROM posts ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_post(post_id: str):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DELETE FROM posts WHERE id=?", (post_id,))
    conn.commit(); conn.close()
    sb = get_supabase()
    if sb:
        try: sb.table("posts").delete().eq("id", post_id).execute()
        except Exception: pass

def get_stats() -> dict:
    conn = sqlite3.connect(str(DB_PATH))
    total  = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    posted = conn.execute("SELECT COUNT(*) FROM posts WHERE status='posted'").fetchone()[0]
    draft  = conn.execute("SELECT COUNT(*) FROM posts WHERE status='draft'").fetchone()[0]
    conn.close()
    return {"total": total, "posted": posted, "draft": draft}
