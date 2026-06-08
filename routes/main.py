# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request, jsonify
import os
from dotenv import load_dotenv
load_dotenv()

main_bp = Blueprint("main", __name__)

# ── 메인 페이지 ───────────────────────────────────────────────
@main_bp.route("/")
def index():
    reuse_id   = request.args.get("reuse")
    reuse_post = None
    if reuse_id:
        from services.database import get_post
        reuse_post = get_post(reuse_id)
    return render_template("index.html", reuse_post=reuse_post)

# ── 설정 페이지 ───────────────────────────────────────────────
@main_bp.route("/settings")
def settings():
    from services.settings_service import get_display_settings
    cfg = get_display_settings()
    return render_template("settings.html", cfg=cfg)

# ── 설정 저장 ─────────────────────────────────────────────────
@main_bp.route("/settings/save", methods=["POST"])
def save_settings():
    """
    관리자 UI → Supabase app_settings 저장 + 로컬 .env 동기화.
    Railway에서도 영구 보존.
    """
    from services.settings_service import save_all_settings

    data = request.json or {}

    # 폼 필드명(snake) → 환경변수명(UPPER) 매핑
    key_map = {
        "anthropic_key":          "ANTHROPIC_API_KEY",
        "openai_key":             "OPENAI_API_KEY",
        "naver_id":               "NAVER_ID",
        "naver_pw":               "NAVER_PW",
        "supabase_url":           "SUPABASE_URL",
        "supabase_key":           "SUPABASE_KEY",
        "post_time":              "AUTO_POST_TIME",
        "category_no":            "NAVER_CATEGORY_NO",
        "category_name":          "NAVER_CATEGORY_NAME",
        "concept":                "BLOG_CONCEPT",
        "image_dir":              "IMAGE_DIR",
        "naver_client_id":        "NAVER_CLIENT_ID",
        "naver_client_secret":    "NAVER_CLIENT_SECRET",
        # 인스타그램
        "instagram_user_id":      "INSTAGRAM_USER_ID",
        "instagram_access_token": "INSTAGRAM_ACCESS_TOKEN",
        "instagram_page_id":      "INSTAGRAM_PAGE_ID",
        # Google Drive
        "gdrive_folder_name":     "GDRIVE_FOLDER_NAME",
        # ngrok 터널
        "ngrok_auth_token":       "NGROK_AUTH_TOKEN",
    }

    # 빈 문자열 / placeholder 제외
    placeholders = {"여기에입력", "sk-ant-...", "sk-proj-...", "eyJ...", ""}
    env_data = {
        key_map[k]: v
        for k, v in data.items()
        if k in key_map and v and v not in placeholders
    }

    result = save_all_settings(env_data)
    return jsonify({"ok": True, "saved": len(result["saved"]), "failed": result["failed"]})

# ── 설정 저장 상태 확인 (헬스체크용) ────────────────────────────
@main_bp.route("/settings/status")
def settings_status():
    """어떤 키가 Supabase에 저장돼 있는지 확인 (값은 노출 안 함)"""
    from services.settings_service import load_all_settings
    keys = list(load_all_settings().keys())
    return jsonify({"stored_keys": keys, "count": len(keys)})
