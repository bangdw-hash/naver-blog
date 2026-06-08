# -*- coding: utf-8 -*-
"""
settings_service.py
─────────────────────────────────────────────────────────────────
설정 관리: Supabase app_settings 테이블 ↔ os.environ 양방향 동기화

우선순위:
  1. Supabase app_settings 테이블 (관리자 UI에서 저장한 값)
  2. .env 파일 / Railway 환경변수 (fallback)

Railway 배포 시 필요한 최소 환경변수:
  SUPABASE_URL, SUPABASE_KEY  → Railway Variables에만 설정
  나머지 키 → 관리자 UI에서 등록 → Supabase에 저장
"""
import os, json
from dotenv import load_dotenv
load_dotenv()

# ── Supabase에 저장 가능한 설정 키 목록 ──────────────────────────
MANAGED_KEYS = {
    # AI API
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    # 네이버 블로그
    "NAVER_ID",
    "NAVER_PW",
    "NAVER_CATEGORY_NO",
    "NAVER_CATEGORY_NAME",
    "NAVER_CLIENT_ID",
    "NAVER_CLIENT_SECRET",
    # 자동화 설정
    "AUTO_POST_TIME",
    "BLOG_CONCEPT",
    "IMAGE_DIR",
    # 인스타그램 (Meta Graph API)
    "INSTAGRAM_USER_ID",
    "INSTAGRAM_ACCESS_TOKEN",
    "INSTAGRAM_PAGE_ID",
    # Google Drive
    "GDRIVE_FOLDER_NAME",
    # ngrok 터널
    "NGROK_AUTH_TOKEN",
    # 기타
    "SECRET_KEY",
}

_client = None

def _get_supabase():
    """Supabase 클라이언트 (lazy init, 실패해도 None 반환)"""
    global _client
    if _client is not None:
        return _client
    try:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")
        if not url or not key:
            return None
        from supabase import create_client
        _client = create_client(url, key)
        return _client
    except Exception:
        return None


def load_all_settings() -> dict:
    """
    Supabase app_settings 테이블에서 모든 설정 로드.
    실패 시 빈 dict 반환 (os.environ fallback은 호출자가 처리).
    """
    sb = _get_supabase()
    if not sb:
        return {}
    try:
        rows = sb.table("app_settings").select("key, value").execute()
        return {r["key"]: r["value"] for r in (rows.data or [])}
    except Exception:
        return {}


def save_setting(key: str, value: str) -> bool:
    """단일 키 Supabase에 upsert"""
    if key not in MANAGED_KEYS:
        return False
    sb = _get_supabase()
    if not sb:
        return False
    try:
        sb.table("app_settings").upsert(
            {"key": key, "value": value},
            on_conflict="key"
        ).execute()
        os.environ[key] = value
        return True
    except Exception:
        return False


def save_all_settings(data: dict) -> dict:
    """
    {env_key: value, ...} 딕셔너리를 받아 Supabase에 일괄 upsert.
    로컬 .env 파일에도 동시 기록.
    성공/실패 키 목록 반환.
    """
    sb = _get_supabase()
    succeeded = []
    failed    = []

    # ── Supabase 저장 ─────────────────────────────────────────
    if sb:
        rows = [
            {"key": k, "value": v}
            for k, v in data.items()
            if k in MANAGED_KEYS and v
        ]
        if rows:
            try:
                sb.table("app_settings").upsert(rows, on_conflict="key").execute()
                succeeded = [r["key"] for r in rows]
            except Exception as e:
                failed = [r["key"] for r in rows]
    else:
        failed = list(data.keys())

    # ── os.environ 즉시 반영 ──────────────────────────────────
    for k, v in data.items():
        if v:
            os.environ[k] = v

    # ── 로컬 .env 파일 갱신 (Railway에서는 /app/.env 없을 수 있음) ─
    _update_env_file(data)

    return {"saved": succeeded, "failed": failed}


def inject_to_env():
    """
    앱 시작 시 호출 — Supabase → os.environ 주입.
    Supabase에 저장된 값이 .env 보다 우선.
    """
    settings = load_all_settings()
    for k, v in settings.items():
        if v:
            os.environ[k] = v
    return len(settings)


def get_display_settings() -> dict:
    """
    설정 페이지 렌더링용: 민감한 값은 마스킹.
    Supabase → os.environ 순으로 참조.
    """
    from_supabase = load_all_settings()

    def _val(key):
        return from_supabase.get(key) or os.getenv(key, "")

    def _mask(val):
        if not val or len(val) < 8:
            return val
        return val[:6] + "..." + val[-4:]

    return {
        # AI
        "ANTHROPIC_API_KEY":      _mask(_val("ANTHROPIC_API_KEY")),
        "OPENAI_API_KEY":         _mask(_val("OPENAI_API_KEY")),
        # Supabase (Bootstrap — Railway에 직접 설정)
        "SUPABASE_URL":           _val("SUPABASE_URL"),
        "SUPABASE_KEY":           _mask(_val("SUPABASE_KEY")),
        # 네이버
        "NAVER_ID":               _val("NAVER_ID"),
        "NAVER_CATEGORY_NO":      _val("NAVER_CATEGORY_NO") or "0",
        "NAVER_CATEGORY_NAME":    _val("NAVER_CATEGORY_NAME") or "전체",
        "NAVER_CLIENT_ID":        _val("NAVER_CLIENT_ID"),
        "NAVER_CLIENT_SECRET":    _mask(_val("NAVER_CLIENT_SECRET")),
        # 자동화
        "AUTO_POST_TIME":         _val("AUTO_POST_TIME") or "09:00",
        "BLOG_CONCEPT":           _val("BLOG_CONCEPT"),
        "IMAGE_DIR":              _val("IMAGE_DIR") or "./uploads/images",
        # 인스타그램
        "INSTAGRAM_USER_ID":      _val("INSTAGRAM_USER_ID"),
        "INSTAGRAM_ACCESS_TOKEN": _mask(_val("INSTAGRAM_ACCESS_TOKEN")),
        "INSTAGRAM_PAGE_ID":      _val("INSTAGRAM_PAGE_ID"),
        # Google Drive
        "GDRIVE_FOLDER_NAME":     _val("GDRIVE_FOLDER_NAME") or "NaverBlog-FoodPhotos",
        # ngrok
        "NGROK_AUTH_TOKEN":       _mask(_val("NGROK_AUTH_TOKEN")),
    }


# ── 내부 헬퍼 ─────────────────────────────────────────────────
def _update_env_file(data: dict):
    """로컬 .env 파일 업데이트 (Railway에서는 파일이 없어도 오류 없이 skip)"""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    try:
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

        updated = set()
        new_lines = []
        for line in lines:
            k = line.split("=")[0].strip() if "=" in line else ""
            if k in data and data[k]:
                new_lines.append(f"{k}={data[k]}\n")
                updated.add(k)
            else:
                new_lines.append(line)
        for k, v in data.items():
            if k not in updated and v:
                new_lines.append(f"{k}={v}\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception:
        pass  # Railway 등 읽기 전용 FS에서는 skip
