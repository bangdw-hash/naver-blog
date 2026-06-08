# -*- coding: utf-8 -*-
"""API 라우터 - 글 생성, 이미지 생성, 포스팅"""
import os, sys, json, threading
from flask import Blueprint, request, jsonify, Response
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services.database import save_post, update_post, get_post, get_stats

api_bp = Blueprint("api", __name__)

# ── SSE 스트림 진행상황 ───────────────────────────────────
progress_store = {}  # job_id → [messages]

def push_progress(job_id, msg, done=False):
    if job_id not in progress_store:
        progress_store[job_id] = []
    progress_store[job_id].append({"msg": msg, "done": done})

@api_bp.route("/progress/<job_id>")
def progress_stream(job_id):
    def generate():
        import time
        sent = 0
        while True:
            msgs = progress_store.get(job_id, [])
            while sent < len(msgs):
                m = msgs[sent]
                yield f"data: {json.dumps(m, ensure_ascii=False)}\n\n"
                sent += 1
                if m.get("done"): return
            time.sleep(0.3)
    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

# ── 블로그 로직 상태 조회 ─────────────────────────────────
@api_bp.route("/logic-status")
def logic_status():
    from services.blog_logic import load_blog_logic
    data = load_blog_logic()
    return jsonify({
        "updated_at": data.get("updated_at", "미설정"),
        "version": data.get("version", "-")
    })

# ── 블로그 로직 최신화 ────────────────────────────────────
@api_bp.route("/update-logic", methods=["POST"])
def update_logic():
    job_id = "logic"
    progress_store[job_id] = []
    def _run():
        from services.blog_logic import update_blog_logic
        result = update_blog_logic(callback=lambda m: push_progress(job_id, m))
        updated_at = result.get("updated_at", "") if result else ""
        push_progress(job_id, json.dumps({"done": True, "updated_at": updated_at}), done=True)
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"job_id": job_id})

# ── 글 생성 ───────────────────────────────────────────────
@api_bp.route("/generate", methods=["POST"])
def generate_content():
    data = request.json or {}
    job_id = data.get("job_id", "gen")
    progress_store[job_id] = []

    def _run():
        try:
            from services.content_gen_v2 import generate_blog_v2
            from services.blog_logic import load_blog_logic
            logic = load_blog_logic()

            result = generate_blog_v2(
                raw_input_text=data.get("raw_input", ""),
                attached_files=data.get("attached_files", []),
                tone=data.get("tone", "친근하게"),
                include_youtube=data.get("include_youtube", True),
                include_map=data.get("include_map", False),
                image_count=data.get("image_count", 5),
                blog_logic=logic.get("guidelines", ""),
                concept=os.getenv("BLOG_CONCEPT", data.get("concept", "")),
                supplement=data.get("supplement", ""),
                previous_content=data.get("previous_content", ""),
                callback=lambda m: push_progress(job_id, m)
            )

            # 초안 저장
            post_id = save_post({**result,
                "raw_input": data.get("raw_input",""),
                "tone": data.get("tone","친근하게"),
                "concept": os.getenv("BLOG_CONCEPT",""),
                "status": "draft"
            })
            result["post_id"] = post_id
            push_progress(job_id, json.dumps({"result": result}, ensure_ascii=False), done=True)

        except Exception as e:
            push_progress(job_id, json.dumps({"error": str(e)}, ensure_ascii=False), done=True)

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"job_id": job_id})

# ── 이미지 생성 ───────────────────────────────────────────
@api_bp.route("/generate-images", methods=["POST"])
def generate_images():
    data = request.json or {}
    job_id = data.get("job_id", "img")
    progress_store[job_id] = []

    def _run():
        try:
            from services.image_gen import generate_images as gen_imgs
            save_dir = data.get("save_dir") or os.getenv("IMAGE_DIR", "./uploads/images")
            paths = gen_imgs(
                post_title=data.get("title", ""),
                post_content=data.get("content", ""),
                save_dir=save_dir,
                image_count=data.get("image_count", 5),
                main_keyword=data.get("main_keyword", ""),
                tags=data.get("tags", []),
                callback=lambda m: push_progress(job_id, m)
            )
            # 이력에 이미지 정보 업데이트
            post_id = data.get("post_id")
            if post_id:
                update_post(post_id, {"images": [p["filename"] for p in paths]})
            push_progress(job_id, json.dumps({"images": paths}, ensure_ascii=False), done=True)
        except Exception as e:
            push_progress(job_id, json.dumps({"error": str(e)}, ensure_ascii=False), done=True)

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"job_id": job_id})

# ── 글 확정 & 저장 ────────────────────────────────────────
@api_bp.route("/confirm", methods=["POST"])
def confirm_post():
    data = request.json or {}
    post_id = data.get("post_id")
    if post_id:
        update_post(post_id, {
            "title":   data.get("title",""),
            "content": data.get("content",""),
            "tags":    data.get("tags",[]),
            "status":  "confirmed"
        })
    return jsonify({"ok": True, "post_id": post_id})

# ── 네이버 포스팅 ─────────────────────────────────────────
@api_bp.route("/post-to-naver", methods=["POST"])
def post_to_naver():
    data = request.json or {}
    post_id = data.get("post_id")
    def _run():
        job_id = f"post_{post_id}"
        progress_store[job_id] = []
        try:
            from services.naver_poster import post_to_naver_blog
            ok = post_to_naver_blog(
                title=data.get("title",""),
                content_html=data.get("content",""),
                tags=data.get("tags",[]),
                category_no=os.getenv("NAVER_CATEGORY_NO","0")
            )
            if ok and post_id:
                update_post(post_id, {"status":"posted"})
            push_progress(job_id, json.dumps({"ok": ok}, ensure_ascii=False), done=True)
        except Exception as e:
            push_progress(job_id, json.dumps({"error": str(e)}, ensure_ascii=False), done=True)
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"job_id": f"post_{post_id}"})

# ── 파일 업로드 ───────────────────────────────────────────
@api_bp.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "파일 없음"}), 400
    f = request.files["file"]
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    os.makedirs(upload_dir, exist_ok=True)
    save_path = os.path.join(upload_dir, f.filename)
    f.save(save_path)

    content = ""
    file_type = "file"

    if f.filename.endswith(".pdf"):
        from services.content_gen_v2 import extract_pdf_text
        content   = extract_pdf_text(save_path)
        file_type = "pdf"
    elif f.filename.endswith((".txt",".md")):
        with open(save_path,"r",encoding="utf-8",errors="ignore") as fp:
            content = fp.read()[:3000]
        file_type = "text"
    elif f.filename.endswith(".json"):
        # credentials.json 등 설정 파일: data/ 에 저장
        data_path = os.path.join("./data", f.filename)
        os.makedirs("./data", exist_ok=True)
        f.stream.seek(0)
        with open(data_path, "wb") as fp:
            fp.write(f.stream.read())
        save_path = data_path
        file_type = "json"

    return jsonify({"name": f.filename, "type": file_type,
                    "content": content, "path": save_path})

# ── 저장소 저장 (폴더에 파일 저장) ──────────────────────────
@api_bp.route("/save-file", methods=["POST"])
def save_file():
    data      = request.json or {}
    title     = data.get("title", "제목없음")
    content   = data.get("content", "")
    tags      = data.get("tags", [])
    folder    = data.get("folder", "./uploads")
    file_fmt  = data.get("format", "txt")  # txt | html

    import re, os
    from datetime import datetime

    # 파일명 생성 (날짜 + 제목)
    date_str  = datetime.now().strftime("%Y%m%d_%H%M")
    safe_name = re.sub(r'[^\w가-힣]', '-', title)[:30].strip('-')
    filename  = f"{date_str}_{safe_name}.{file_fmt}"

    try:
        os.makedirs(folder, exist_ok=True)
        save_path = os.path.join(folder, filename)

        if file_fmt == "html":
            tags_html = " ".join(f"#{t}" for t in tags) if tags else ""
            body = content.replace("\n", "<br>\n")
            html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8">
<title>{title}</title>
<style>body{{font-family:'Noto Sans KR',sans-serif;max-width:800px;margin:40px auto;line-height:1.8;padding:20px;}}
h1{{color:#1a1b23;}}
.tags{{color:#6b7280;font-size:13px;margin-bottom:20px;}}
.content{{font-size:15px;}}
</style></head>
<body>
<h1>{title}</h1>
<div class="tags">{tags_html}</div>
<div class="content">{body}</div>
</body></html>"""
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(html)
        else:
            tags_str = " ".join(f"#{t}" for t in tags) if tags else ""
            text = f"[제목]\n{title}\n\n[태그]\n{tags_str}\n\n{'='*40}\n[본문]\n{'='*40}\n\n{content}"
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(text)

        return jsonify({"ok": True, "path": save_path, "filename": filename})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── 통계 ─────────────────────────────────────────────────
@api_bp.route("/stats")
def stats():
    return jsonify(get_stats())

# ══════════════════════════════════════════════════════════════
#  맛집 로직 API
# ══════════════════════════════════════════════════════════════
@api_bp.route("/food-logic-status")
def food_logic_status():
    from services.food_logic import load_food_logic
    d = load_food_logic()
    return jsonify({"updated_at": d.get("updated_at"), "version": d.get("version","0")})

@api_bp.route("/update-food-logic", methods=["POST"])
def update_food_logic_api():
    job_id = "food_logic"
    progress_store[job_id] = []
    def _run():
        from services.food_logic import update_food_logic
        result = update_food_logic(callback=lambda m: push_progress(job_id, m))
        updated_at = result.get("updated_at","") if result else ""
        push_progress(job_id, json.dumps({"done":True,"updated_at":updated_at}), done=True)
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"job_id": job_id})

# ── 영수증 리뷰 생성 ──────────────────────────────────────────
@api_bp.route("/generate-receipt-review", methods=["POST"])
def generate_receipt_review_api():
    data   = request.get_json(silent=True) or {}
    job_id = data.get("job_id", "rcpt_" + str(__import__('time').time_ns()))
    progress_store[job_id] = []
    def _run():
        try:
            from services.naver_receipt import generate_receipt_review
            result = generate_receipt_review(
                place_name   = data.get("place_name",""),
                place_addr   = data.get("place_addr",""),
                visit_date   = data.get("visit_date",""),
                menu_items   = data.get("menu_items",[]),
                total_amount = int(data.get("total_amount",0) or 0),
                rating_taste = int(data.get("rating_taste",3)),
                rating_mood  = int(data.get("rating_mood",3)),
                memo         = data.get("memo",""),
                callback     = lambda m: push_progress(job_id, m)
            )
            push_progress(job_id, json.dumps({"result":result},ensure_ascii=False), done=True)
        except Exception as e:
            push_progress(job_id, json.dumps({"error":str(e)},ensure_ascii=False), done=True)
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"job_id": job_id})

# ══════════════════════════════════════════════════════════════
#  맛집 탐방 API
# ══════════════════════════════════════════════════════════════

# ── 네이버 장소 검색 ─────────────────────────────────────────
@api_bp.route("/search-place", methods=["GET","POST"])
def search_place_api():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        q = body.get("query","") or body.get("q","")
    else:
        q = request.args.get("q","")
    if not q:
        return jsonify({"error": "검색어 필요"}), 400
    from services.naver_place import search_place
    results = search_place(q, display=6)
    return jsonify({"items": results})

# ── 사진 업로드 (Supabase Storage + 선택적 Google Drive) ──────
@api_bp.route("/upload-photo", methods=["POST"])
def upload_photo_api():
    if "file" not in request.files:
        return jsonify({"error": "파일 없음"}), 400

    f          = request.files["file"]
    storage    = request.form.get("storage", "supabase")  # supabase | gdrive | both
    place_name = request.form.get("place_name", "unknown")
    visit_date = request.form.get("visit_date", "")[:10].replace("-","")

    import re
    from datetime import datetime
    if not visit_date:
        visit_date = datetime.now().strftime("%Y%m%d")
    safe_place = re.sub(r'[^\w가-힣]', '', place_name)[:10] or "food"
    ext        = os.path.splitext(f.filename)[1].lower() or ".jpg"
    idx        = request.form.get("index", "1")
    filename   = f"{visit_date}_{safe_place}_{idx.zfill(3)}{ext}"
    content_type = f.content_type or "image/jpeg"

    from services.photo_storage import upload_photo
    result = upload_photo(f.read(), filename, content_type, storage=storage)
    return jsonify(result)

# ── 사진 다운로드 프록시 ──────────────────────────────────────
@api_bp.route("/download-photo")
def download_photo_proxy():
    """Supabase URL에서 이미지를 프록시해 다운로드 (CORS 우회)"""
    import requests as req_lib
    from flask import send_file
    import io
    url = request.args.get("url","")
    filename = request.args.get("name","photo.jpg")
    if not url:
        return jsonify({"error": "url 필요"}), 400
    try:
        r = req_lib.get(url, timeout=15)
        r.raise_for_status()
        return send_file(
            io.BytesIO(r.content),
            as_attachment=True,
            download_name=filename,
            mimetype=r.headers.get("Content-Type","image/jpeg")
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── 맛집 글 생성 ─────────────────────────────────────────────
@api_bp.route("/generate-food", methods=["POST"])
def generate_food():
    data   = request.json or {}
    job_id = data.get("job_id", "food_" + str(__import__('time').time_ns()))
    progress_store[job_id] = []

    def _run():
        try:
            from services.food_gen import generate_food_blog
            result = generate_food_blog(
                place_name   = data.get("place_name",""),
                place_addr   = data.get("place_addr",""),
                place_link   = data.get("place_link",""),
                place_cat    = data.get("place_cat",""),
                visit_date   = data.get("visit_date",""),
                rating_taste = data.get("rating_taste",3),
                rating_mood  = data.get("rating_mood",3),
                price_range  = data.get("price_range",""),
                revisit      = data.get("revisit","예"),
                party_size   = data.get("party_size","2"),
                memo         = data.get("memo",""),
                photos       = data.get("photos",[]),
                callback     = lambda m: push_progress(job_id, m)
            )
            # 초안 저장
            from services.food_db import save_food_post
            post_id = save_food_post({**data, **result})
            result["post_id"] = post_id
            push_progress(job_id, json.dumps({"result": result}, ensure_ascii=False), done=True)
        except Exception as e:
            push_progress(job_id, json.dumps({"error": str(e)}, ensure_ascii=False), done=True)

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"job_id": job_id})

# ── 맛집 글 저장/수정 ────────────────────────────────────────
@api_bp.route("/save-food", methods=["POST"])
def save_food_api():
    data = request.json or {}
    post_id = data.get("post_id")
    from services.food_db import save_food_post, update_food_post
    if post_id:
        update_food_post(post_id, data)
    else:
        post_id = save_food_post(data)
    return jsonify({"ok": True, "post_id": post_id})

# ── 맛집 글 목록 ─────────────────────────────────────────────
@api_bp.route("/food-posts")
def list_food_api():
    from services.food_db import list_food_posts
    limit  = int(request.args.get("limit",50))
    offset = int(request.args.get("offset",0))
    return jsonify(list_food_posts(limit, offset))

# ── 맛집 글 단건 ─────────────────────────────────────────────
@api_bp.route("/food-posts/<post_id>")
def get_food_api(post_id):
    from services.food_db import get_food_post
    return jsonify(get_food_post(post_id))

# ── 맛집 글 삭제 ─────────────────────────────────────────────
@api_bp.route("/food-posts/<post_id>", methods=["DELETE"])
def delete_food_api(post_id):
    from services.food_db import delete_food_post
    delete_food_post(post_id)
    return jsonify({"ok": True})

# ══════════════════════════════════════════════════════════════
#  동기화 API
# ══════════════════════════════════════════════════════════════

@api_bp.route("/sync-status")
def sync_status_api():
    from services.sync_service import get_sync_status
    return jsonify(get_sync_status())

@api_bp.route("/sync", methods=["POST"])
def sync_api():
    data      = request.json or {}
    direction = data.get("direction", "pull")  # pull | push | both
    job_id    = "sync_" + str(__import__('time').time_ns())
    progress_store[job_id] = []

    def _run():
        from services.sync_service import full_sync
        result = full_sync(direction, callback=lambda m: push_progress(job_id, m))
        push_progress(job_id, json.dumps({"sync_done": True, **result}, ensure_ascii=False), done=True)

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"job_id": job_id})

# ── Google Drive OAuth ────────────────────────────────────────
@api_bp.route("/gdrive-auth")
def gdrive_auth():
    from services.photo_storage import start_gdrive_oauth
    url = start_gdrive_oauth()
    if not url:
        return jsonify({"error": "data/gdrive_credentials.json 파일이 없습니다."}), 400
    return jsonify({"auth_url": url})

@api_bp.route("/gdrive-callback")
def gdrive_callback():
    code = request.args.get("code","")
    from services.photo_storage import finish_gdrive_oauth
    ok = finish_gdrive_oauth(code)
    if ok:
        return "<script>window.close();</script><p>✅ Google Drive 연결 완료! 이 창을 닫으세요.</p>"
    return "<p>❌ 연결 실패. 다시 시도해주세요.</p>", 400

@api_bp.route("/gdrive-status")
def gdrive_status():
    from services.photo_storage import is_gdrive_connected
    return jsonify({"connected": is_gdrive_connected()})
