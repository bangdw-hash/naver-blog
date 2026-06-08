# -*- coding: utf-8 -*-
"""
app.py - 네이버 블로그 자동화 웹앱 메인
실행: python app.py
접속: http://localhost:5000 (PC)
     http://[내PC IP]:5000 (모바일 - 같은 WiFi)
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
load_dotenv()

# API 키 환경변수 설정
if os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("SECRET_KEY", "naver-blog-secret-2025")
CORS(app)

# 업로드 폴더 생성
os.makedirs(os.getenv("UPLOAD_DIR", "./uploads"), exist_ok=True)
os.makedirs(os.getenv("IMAGE_DIR", "./uploads/images"), exist_ok=True)

# ── 라우터 등록 ───────────────────────────────────────────
from routes.main    import main_bp
from routes.api     import api_bp
from routes.history import history_bp

app.register_blueprint(main_bp)
app.register_blueprint(api_bp,     url_prefix="/api")
app.register_blueprint(history_bp, url_prefix="/history")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"""
╔══════════════════════════════════════╗
║   네이버 블로그 자동화 웹앱 시작     ║
╠══════════════════════════════════════╣
║  PC 접속:     http://localhost:{port}   ║
║  모바일 접속: http://[PC IP]:{port}     ║
║  (같은 WiFi 연결 필요)               ║
╚══════════════════════════════════════╝
    """)
    app.run(host="0.0.0.0", port=port, debug=True)
