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

# ── 블로그 로직 최신화 ────────────────────────────────────
@api_bp.route("/update-logic", methods=["POST"])
def update_logic():
    job_id = "logic"
    progress_store[job_id] = []
    def _run():
        from services.blog_logic import update_blog_logic
        update_blog_logic(callback=lambda m: push_progress(job_id, m))
        push_progress(job_id, "완료!", done=True)
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
    if f.filename.endswith(".pdf"):
        from services.content_gen_v2 import extract_pdf_text
        content = extract_pdf_text(save_path)
    elif f.filename.endswith((".txt",".md")):
        with open(save_path,"r",encoding="utf-8",errors="ignore") as fp:
            content = fp.read()[:3000]

    return jsonify({"name": f.filename, "type": "pdf" if f.filename.endswith(".pdf") else "text",
                    "content": content, "path": save_path})

# ── 통계 ─────────────────────────────────────────────────
@api_bp.route("/stats")
def stats():
    return jsonify(get_stats())
