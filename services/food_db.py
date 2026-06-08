# -*- coding: utf-8 -*-
"""
food_db.py - 맛집 탐방 게시물 SQLite + Supabase 이중 저장
"""
import os, json, sqlite3, uuid
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

DB_PATH = Path(os.path.dirname(__file__)) / ".." / "data" / "food.db"

def init_food_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
    CREATE TABLE IF NOT EXISTS food_posts (
        id           TEXT PRIMARY KEY,
        place_name   TEXT,
        place_addr   TEXT,
        place_road   TEXT,
        place_link   TEXT,
        place_tel    TEXT,
        place_cat    TEXT,
        mapx         TEXT,
        mapy         TEXT,
        visit_date   TEXT,
        rating_taste INTEGER DEFAULT 3,
        rating_mood  INTEGER DEFAULT 3,
        price_range  TEXT,
        revisit      TEXT,
        party_size   TEXT,
        memo         TEXT,
        photos       TEXT DEFAULT '[]',
        title        TEXT,
        content      TEXT,
        tags         TEXT DEFAULT '[]',
        status       TEXT DEFAULT 'draft',
        created_at   TEXT
    )""")
    conn.commit(); conn.close()

init_food_db()

def _get_supabase():
    url = os.getenv("SUPABASE_URL","")
    key = os.getenv("SUPABASE_KEY","")
    if not url or not key: return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except: return None

def save_food_post(data: dict) -> str:
    post_id = str(uuid.uuid4())
    now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
    INSERT INTO food_posts
      (id,place_name,place_addr,place_road,place_link,place_tel,place_cat,
       mapx,mapy,visit_date,rating_taste,rating_mood,price_range,revisit,
       party_size,memo,photos,title,content,tags,status,created_at)
    VALUES
      (:id,:place_name,:place_addr,:place_road,:place_link,:place_tel,:place_cat,
       :mapx,:mapy,:visit_date,:rating_taste,:rating_mood,:price_range,:revisit,
       :party_size,:memo,:photos,:title,:content,:tags,:status,:created_at)
    """, {
        "id":           post_id,
        "place_name":   data.get("place_name",""),
        "place_addr":   data.get("place_addr",""),
        "place_road":   data.get("place_road",""),
        "place_link":   data.get("place_link",""),
        "place_tel":    data.get("place_tel",""),
        "place_cat":    data.get("place_cat",""),
        "mapx":         data.get("mapx",""),
        "mapy":         data.get("mapy",""),
        "visit_date":   data.get("visit_date", now[:10]),
        "rating_taste": data.get("rating_taste", 3),
        "rating_mood":  data.get("rating_mood", 3),
        "price_range":  data.get("price_range",""),
        "revisit":      data.get("revisit","예"),
        "party_size":   data.get("party_size","2"),
        "memo":         data.get("memo",""),
        "photos":       json.dumps(data.get("photos",[]), ensure_ascii=False),
        "title":        data.get("title",""),
        "content":      data.get("content",""),
        "tags":         json.dumps(data.get("tags",[]), ensure_ascii=False),
        "status":       data.get("status","draft"),
        "created_at":   now,
    })
    conn.commit(); conn.close()

    # Supabase 동기화
    sb = _get_supabase()
    if sb:
        try:
            sb.table("food_posts").upsert({
                "id": post_id, "place_name": data.get("place_name",""),
                "place_addr": data.get("place_addr",""), "visit_date": data.get("visit_date", now[:10]),
                "photos": data.get("photos",[]), "title": data.get("title",""),
                "content": data.get("content",""), "tags": data.get("tags",[]),
                "memo": data.get("memo",""), "status": data.get("status","draft"),
                "created_at": now,
            }).execute()
        except: pass
    return post_id

def update_food_post(post_id: str, data: dict):
    set_parts = []
    vals = {}
    for k, v in data.items():
        if k in ("photos","tags") and isinstance(v, list):
            v = json.dumps(v, ensure_ascii=False)
        set_parts.append(f"{k}=:{k}")
        vals[k] = v
    if not set_parts: return
    vals["id"] = post_id
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(f"UPDATE food_posts SET {','.join(set_parts)} WHERE id=:id", vals)
    conn.commit(); conn.close()

    sb = _get_supabase()
    if sb:
        try:
            upd = {k: v for k,v in data.items() if k not in ("photos","tags")}
            if "photos" in data: upd["photos"] = data["photos"] if isinstance(data["photos"],list) else json.loads(data["photos"])
            if "tags"   in data: upd["tags"]   = data["tags"]   if isinstance(data["tags"],list)   else json.loads(data["tags"])
            sb.table("food_posts").update(upd).eq("id", post_id).execute()
        except: pass

def get_food_post(post_id: str) -> dict:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM food_posts WHERE id=?", (post_id,)).fetchone()
    conn.close()
    if not row: return {}
    d = dict(row)
    for k in ("photos","tags"):
        try: d[k] = json.loads(d[k] or "[]")
        except: d[k] = []
    return d

def list_food_posts(limit=50, offset=0) -> list:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id,place_name,place_addr,visit_date,rating_taste,rating_mood,status,created_at,title FROM food_posts ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_food_post(post_id: str):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DELETE FROM food_posts WHERE id=?", (post_id,))
    conn.commit(); conn.close()
    sb = _get_supabase()
    if sb:
        try: sb.table("food_posts").delete().eq("id", post_id).execute()
        except: pass
