# -*- coding: utf-8 -*-
"""
app.py - 네이버 블로그 자동화 웹앱 메인
실행: python app.py
접속: http://localhost:5000 (PC)
     http://[내PC IP]:5000 (모바일 - 같은 WiFi)
"""
import sys, os
# Railway 환경에서는 utf-8 재설정이 필요 없을 수 있으므로 안전하게 처리
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
load_dotenv()

# Railway 배포 환경: /data 볼륨이 없으면 로컬 ./data 사용
# 환경변수 RAILWAY_ENVIRONMENT 가 있으면 Railway
IS_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PUBLIC_DOMAIN"))

# API 키 환경변수 설정
if os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("SECRET_KEY", "naver-blog-secret-2025")
CORS(app, resources={r"/*": {"origins": "*"}})

# ── Supabase → os.environ 설정 주입 (Railway 배포 포함) ───────
try:
    from services.settings_service import inject_to_env
    n = inject_to_env()
    if n:
        print(f"[settings] Supabase에서 {n}개 설정 로드됨")
    # secret_key도 Supabase에 저장된 값으로 갱신
    if os.getenv("SECRET_KEY"):
        app.secret_key = os.getenv("SECRET_KEY")
except Exception as _e:
    print(f"[settings] Supabase 설정 로드 skip: {_e}")

# ── 모든 응답에 권한 허용 헤더 추가 ──────────────────────────
@app.after_request
def add_permission_headers(response):
    response.headers["Permissions-Policy"] = (
        "camera=*, clipboard-read=*, clipboard-write=*"
    )
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    response.headers["Cross-Origin-Embedder-Policy"] = "unsafe-none"
    return response

# 업로드 폴더 생성
os.makedirs(os.getenv("UPLOAD_DIR", "./uploads"), exist_ok=True)
os.makedirs(os.getenv("IMAGE_DIR", "./uploads/images"), exist_ok=True)
os.makedirs("./uploads/food", exist_ok=True)
os.makedirs("./data", exist_ok=True)

# ── 라우터 등록 ───────────────────────────────────────────
from routes.main    import main_bp
from routes.api     import api_bp
from routes.history import history_bp
from routes.remote  import remote_bp

app.register_blueprint(main_bp)
app.register_blueprint(api_bp,     url_prefix="/api")
app.register_blueprint(history_bp, url_prefix="/history")
app.register_blueprint(remote_bp)

# ── 맛집 DB 초기화 ────────────────────────────────────────
try:
    from services.food_db import init_food_db
    init_food_db()
except Exception as e:
    print(f"[food_db] 초기화 오류: {e}")

# ── 자동 동기화 시작 (5분마다) ────────────────────────────
import threading
def _start_sync():
    try:
        from services.sync_service import start_auto_sync
        start_auto_sync(interval_sec=300)
    except Exception as e:
        print(f"[sync] 자동 동기화 시작 오류: {e}")

threading.Thread(target=_start_sync, daemon=True).start()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    # 현재 IP 표시
    import socket
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except:
        ip = "알 수 없음"
    print(f"""
╔══════════════════════════════════════════╗
║     네이버 블로그 자동화 웹앱 시작       ║
╠══════════════════════════════════════════╣
║  PC 접속:      http://localhost:{port}     ║
║  모바일 접속:  http://{ip}:{port}  ║
║  (같은 WiFi 연결 필요)                   ║
║  자동 동기화:  5분마다 백그라운드 실행    ║
╚══════════════════════════════════════════╝
    """)
    app.run(host="0.0.0.0", port=port, debug=True)
