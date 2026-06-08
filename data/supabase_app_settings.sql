-- ══════════════════════════════════════════════════════════════
-- Supabase SQL Editor에서 실행하세요
-- 앱 설정 영구 저장 테이블 (Railway 재배포 후에도 유지)
-- ══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS app_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 업데이트 시 자동으로 updated_at 갱신
CREATE OR REPLACE FUNCTION update_app_settings_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_app_settings_updated ON app_settings;
CREATE TRIGGER trg_app_settings_updated
    BEFORE UPDATE ON app_settings
    FOR EACH ROW EXECUTE FUNCTION update_app_settings_timestamp();

-- RLS 비활성화 (서버 사이드에서만 접근)
ALTER TABLE app_settings DISABLE ROW LEVEL SECURITY;

-- 확인
SELECT 'app_settings 테이블 생성 완료' AS result;
