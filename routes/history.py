# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, jsonify, request
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services.database import list_posts, get_post, delete_post, update_post

history_bp = Blueprint("history", __name__)

@history_bp.route("/")
def history_list():
    posts = list_posts(limit=100)

    # 맛집 게시물 로드
    food_posts = []
    try:
        from services.food_db import list_food_posts
        food_posts = list_food_posts(limit=100)
    except Exception:
        pass

    return render_template("history.html", posts=posts, food_posts=food_posts)

@history_bp.route("/<post_id>")
def post_detail(post_id):
    post = get_post(post_id)
    if not post:
        return "포스트를 찾을 수 없습니다.", 404
    return render_template("post_detail.html", post=post)

@history_bp.route("/<post_id>/json")
def post_json(post_id):
    return jsonify(get_post(post_id))

@history_bp.route("/<post_id>/delete", methods=["POST"])
def delete(post_id):
    delete_post(post_id)
    return jsonify({"ok": True})

@history_bp.route("/<post_id>/update-status", methods=["POST"])
def update_status(post_id):
    data = request.json or {}
    update_post(post_id, {"status": data.get("status", "draft")})
    return jsonify({"ok": True})

# ── 맛집 게시물 삭제 ─────────────────────────────────────────
@history_bp.route("/food/<post_id>/delete", methods=["POST"])
def delete_food(post_id):
    try:
        from services.food_db import delete_food_post
        delete_food_post(post_id)
    except Exception:
        pass
    return jsonify({"ok": True})
