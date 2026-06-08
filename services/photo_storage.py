# -*- coding: utf-8 -*-
"""
photo_storage.py - 사진 업로드 (Supabase Storage 기본 + Google Drive 선택)
"""
import os, io, json, mimetypes
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

SUPABASE_BUCKET = "food-photos"
GDRIVE_TOKEN_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "gdrive_token.json")
GDRIVE_CREDS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "gdrive_credentials.json")

# ── Supabase Storage ─────────────────────────────────────────
def _get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    from supabase import create_client
    return create_client(url, key)

def _ensure_bucket(sb):
    """버킷 없으면 자동 생성"""
    try:
        buckets = sb.storage.list_buckets()
        names = [b.name for b in buckets]
        if SUPABASE_BUCKET not in names:
            sb.storage.create_bucket(SUPABASE_BUCKET, options={"public": True})
    except Exception as e:
        pass  # 이미 있거나 권한 문제

def upload_photo_supabase(file_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> dict:
    """Supabase Storage에 사진 업로드 → 공개 URL 반환"""
    sb = _get_supabase()
    if not sb:
        return {"error": "Supabase 설정 없음", "storage": "supabase"}

    _ensure_bucket(sb)

    try:
        # 중복 파일명 방지
        safe_name = filename.replace(" ", "_")
        res = sb.storage.from_(SUPABASE_BUCKET).upload(
            path=safe_name,
            file=file_bytes,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        # 공개 URL
        pub = sb.storage.from_(SUPABASE_BUCKET).get_public_url(safe_name)
        return {
            "filename": safe_name,
            "url": pub,
            "storage": "supabase",
            "bucket": SUPABASE_BUCKET,
        }
    except Exception as e:
        return {"error": str(e), "storage": "supabase"}


# ── Google Drive ──────────────────────────────────────────────
GDRIVE_FOLDER_NAME = "NaverBlog-FoodPhotos"
_gdrive_folder_id  = None

def _get_gdrive_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    token_path = Path(GDRIVE_TOKEN_FILE)
    if not token_path.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES_GDRIVE)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return build("drive", "v3", credentials=creds)

SCOPES_GDRIVE = ["https://www.googleapis.com/auth/drive.file"]

def start_gdrive_oauth() -> str:
    """OAuth2 인증 URL 반환 (설정 페이지에서 사용)"""
    creds_path = Path(GDRIVE_CREDS_FILE)
    if not creds_path.exists():
        return ""
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_secrets_file(
        str(creds_path), scopes=SCOPES_GDRIVE,
        redirect_uri="http://localhost:5000/api/gdrive-callback"
    )
    auth_url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true")
    return auth_url

def finish_gdrive_oauth(code: str) -> bool:
    """OAuth2 콜백 처리 - 토큰 저장"""
    creds_path = Path(GDRIVE_CREDS_FILE)
    if not creds_path.exists():
        return False
    try:
        from google_auth_oauthlib.flow import Flow
        flow = Flow.from_client_secrets_file(
            str(creds_path), scopes=SCOPES_GDRIVE,
            redirect_uri="http://localhost:5000/api/gdrive-callback"
        )
        flow.fetch_token(code=code)
        Path(GDRIVE_TOKEN_FILE).parent.mkdir(exist_ok=True)
        with open(GDRIVE_TOKEN_FILE, "w") as f:
            f.write(flow.credentials.to_json())
        return True
    except Exception as e:
        return False

def _get_or_create_gdrive_folder(service) -> str:
    global _gdrive_folder_id
    if _gdrive_folder_id:
        return _gdrive_folder_id
    results = service.files().list(
        q=f"name='{GDRIVE_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name)"
    ).execute()
    items = results.get("files", [])
    if items:
        _gdrive_folder_id = items[0]["id"]
        return _gdrive_folder_id
    # 폴더 생성
    meta = {"name": GDRIVE_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"}
    folder = service.files().create(body=meta, fields="id").execute()
    _gdrive_folder_id = folder["id"]
    # 공개 권한
    service.permissions().create(fileId=_gdrive_folder_id, body={"type": "anyone", "role": "reader"}).execute()
    return _gdrive_folder_id

def upload_photo_gdrive(file_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> dict:
    """Google Drive에 사진 업로드 → 공개 URL 반환"""
    try:
        from googleapiclient.http import MediaInMemoryUpload
        service = _get_gdrive_service()
        if not service:
            return {"error": "Google Drive 인증 필요", "storage": "gdrive"}

        folder_id = _get_or_create_gdrive_folder(service)
        media = MediaInMemoryUpload(file_bytes, mimetype=content_type)
        meta  = {"name": filename, "parents": [folder_id]}
        f = service.files().create(body=meta, media_body=media, fields="id,webViewLink,webContentLink").execute()

        # 파일 공개
        service.permissions().create(fileId=f["id"], body={"type": "anyone", "role": "reader"}).execute()
        # 직접 다운로드 URL
        direct_url = f"https://drive.google.com/uc?id={f['id']}&export=download"
        return {
            "filename": filename,
            "url": direct_url,
            "view_url": f.get("webViewLink", ""),
            "file_id": f["id"],
            "storage": "gdrive",
        }
    except Exception as e:
        return {"error": str(e), "storage": "gdrive"}

def is_gdrive_connected() -> bool:
    """Google Drive 인증 여부"""
    return Path(GDRIVE_TOKEN_FILE).exists()

# ── 통합 업로드 ───────────────────────────────────────────────
def upload_photo(file_bytes: bytes, filename: str, content_type: str = "image/jpeg",
                 storage: str = "supabase") -> dict:
    """storage='supabase' 또는 'gdrive' 또는 'both'"""
    results = {}
    if storage in ("supabase", "both"):
        results["supabase"] = upload_photo_supabase(file_bytes, filename, content_type)
    if storage in ("gdrive", "both"):
        results["gdrive"] = upload_photo_gdrive(file_bytes, filename, content_type)

    # 단일 결과 반환
    if storage == "supabase":
        return results["supabase"]
    if storage == "gdrive":
        return results["gdrive"]
    # both: 첫 번째 성공한 것 + 두 번째 url 포함
    main = results.get("supabase", {})
    gdrive = results.get("gdrive", {})
    if "error" not in main:
        if "error" not in gdrive:
            main["gdrive_url"] = gdrive.get("url", "")
        return main
    return gdrive
