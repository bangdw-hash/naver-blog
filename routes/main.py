# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request, jsonify, send_file
import os
from dotenv import load_dotenv
load_dotenv()

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def index():
    return render_template("index.html")

@main_bp.route("/settings")
def settings():
    cfg = {
        "ANTHROPIC_API_KEY": _mask(os.getenv("ANTHROPIC_API_KEY","")),
        "OPENAI_API_KEY":    _mask(os.getenv("OPENAI_API_KEY","")),
        "NAVER_ID":          os.getenv("NAVER_ID",""),
        "SUPABASE_URL":      os.getenv("SUPABASE_URL",""),
        "SUPABASE_KEY":      _mask(os.getenv("SUPABASE_KEY","")),
        "AUTO_POST_TIME":    os.getenv("AUTO_POST_TIME","09:00"),
        "NAVER_CATEGORY_NO": os.getenv("NAVER_CATEGORY_NO","0"),
        "NAVER_CATEGORY_NAME":os.getenv("NAVER_CATEGORY_NAME","전체"),
        "BLOG_CONCEPT":      os.getenv("BLOG_CONCEPT",""),
        "IMAGE_DIR":         os.getenv("IMAGE_DIR","./uploads/images"),
    }
    return render_template("settings.html", cfg=cfg)

@main_bp.route("/settings/save", methods=["POST"])
def save_settings():
    """설정 저장 - .env 파일 업데이트"""
    data = request.json or {}
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    key_map = {
        "anthropic_key": "ANTHROPIC_API_KEY",
        "openai_key":    "OPENAI_API_KEY",
        "naver_id":      "NAVER_ID",
        "naver_pw":      "NAVER_PW",
        "supabase_url":  "SUPABASE_URL",
        "supabase_key":  "SUPABASE_KEY",
        "post_time":     "AUTO_POST_TIME",
        "category_no":   "NAVER_CATEGORY_NO",
        "category_name": "NAVER_CATEGORY_NAME",
        "concept":       "BLOG_CONCEPT",
        "image_dir":     "IMAGE_DIR",
    }
    updates = {key_map[k]: v for k,v in data.items() if k in key_map and v}

    # 기존 값 업데이트 또는 추가
    updated_keys = set()
    new_lines = []
    for line in lines:
        key = line.split("=")[0].strip() if "=" in line else ""
        if key in updates:
            new_lines.append(f"{key}={updates[key]}\n")
            updated_keys.add(key)
            os.environ[key] = updates[key]
        else:
            new_lines.append(line)
    for k, v in updates.items():
        if k not in updated_keys:
            new_lines.append(f"{k}={v}\n")
            os.environ[k] = v

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    return jsonify({"ok": True})

def _mask(val):
    if not val or len(val) < 8: return val
    return val[:6] + "..." + val[-4:]
