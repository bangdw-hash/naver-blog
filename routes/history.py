# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, jsonify, request
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services.database import list_posts, get_post, delete_post, update_post

history_bp = Blueprint("history", __name__)

@history_bp.route("/")
def history_list():
    posts = list_posts(limit=50)
    return render_template("history.html", posts=posts)

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
    update_post(post_id, {"status": data.get("status","draft")})
    return jsonify({"ok": True})
