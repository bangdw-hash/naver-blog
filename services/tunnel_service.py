# -*- coding: utf-8 -*-
"""
tunnel_service.py — ngrok 터널 관리
앱 실행 시 자동으로 공개 HTTPS URL을 생성합니다.

사용:
  start_tunnel(port=5000)  → 터널 시작, 공개 URL 반환
  get_public_url()         → 현재 공개 URL 반환 (없으면 None)
  stop_tunnel()            → 터널 중지
"""
import os
import threading

_tunnel      = None   # pyngrok tunnel 객체
_public_url  = None   # https://xxxx.ngrok-free.app
_lock        = threading.Lock()


def start_tunnel(port: int = 5000) -> str | None:
    """
    ngrok 터널 시작. 공개 URL 반환.
    NGROK_AUTH_TOKEN 환경변수 있으면 인증된 터널 사용 (고정 도메인 가능).
    없으면 무인증 임시 URL (매 실행마다 바뀜).
    """
    global _tunnel, _public_url

    with _lock:
        if _public_url:
            return _public_url

        try:
            from pyngrok import ngrok, conf

            auth_token = os.getenv("NGROK_AUTH_TOKEN", "")
            if auth_token:
                ngrok.set_auth_token(auth_token)

            # HTTPS 터널 열기
            tunnel      = ngrok.connect(port, "http")
            _public_url = tunnel.public_url
            _tunnel     = tunnel

            # http → https 강제
            if _public_url and _public_url.startswith("http://"):
                _public_url = _public_url.replace("http://", "https://", 1)

            print(f"\n🌐 ngrok 공개 URL: {_public_url}")
            print(f"   모바일에서 이 URL로 어디서든 접속 가능합니다!\n")
            return _public_url

        except Exception as e:
            print(f"[tunnel] ngrok 시작 실패: {e}")
            if "authtoken" in str(e).lower() or "ERR_NGROK_108" in str(e):
                print("[tunnel] ngrok 무료 계정 토큰이 필요합니다.")
                print("  → https://dashboard.ngrok.com/get-started/your-authtoken 에서 발급 후")
                print("  → 설정 페이지 또는 .env에 NGROK_AUTH_TOKEN=xxxx 입력하세요.")
            return None


def get_public_url() -> str | None:
    """현재 활성 ngrok 공개 URL"""
    return _public_url


def stop_tunnel():
    global _tunnel, _public_url
    with _lock:
        try:
            if _tunnel:
                from pyngrok import ngrok
                ngrok.disconnect(_tunnel.public_url)
        except Exception:
            pass
        _tunnel     = None
        _public_url = None


def get_status() -> dict:
    """터널 상태 딕셔너리"""
    url = get_public_url()
    return {
        "active":     bool(url),
        "public_url": url,
        "type":       "ngrok" if url else None,
    }
