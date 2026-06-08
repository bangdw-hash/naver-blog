# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os, json, re
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
load_dotenv()

NAVER_ID    = os.getenv("NAVER_ID")
COOKIE_FILE = "naver_cookies.json"

def post_to_naver_blog(title: str, content_html: str, tags: list, category_no: str = "0") -> bool:
    if not os.path.exists(COOKIE_FILE):
        print("[오류] 쿠키 파일 없음")
        return False
    with open(COOKIE_FILE, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False,
                                     args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        context.add_cookies(cookies)
        page = context.new_page()

        try:
            print("[1/5] 로그인 상태 확인...")
            page.goto("https://www.naver.com", wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            print("[1/5] 로그인 확인")

            print("[2/5] 글쓰기 페이지 진입...")
            url = f"https://blog.naver.com/PostWriteForm.naver?blogId={NAVER_ID}&categoryNo={category_no}"
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            if "login" in page.url:
                print("[경고] 세션 만료")
                return False
            print("[2/5] 글쓰기 페이지 진입")

            print("[3/5] 제목 입력...")
            for frame in page.frames:
                try:
                    body = frame.locator("body[contenteditable='true']")
                    if body.count() > 0:
                        ph = body.get_attribute("data-placeholder") or ""
                        if "제목" in ph:
                            body.click(); body.type(title, delay=50)
                            print(f"[3/5] 제목: {title}")
                            break
                except Exception: continue
            page.wait_for_timeout(500)

            print("[4/5] 본문 입력...")
            plain = re.sub(r'<h[1-6][^>]*>', '\n\n', content_html)
            plain = re.sub(r'</h[1-6]>', '\n', plain)
            plain = re.sub(r'<p[^>]*>', '', plain)
            plain = re.sub(r'</p>', '\n\n', plain)
            plain = re.sub(r'<br\s*/?>', '\n', plain)
            plain = re.sub(r'<[^>]+>', '', plain)
            plain = re.sub(r'\n{3,}', '\n\n', plain).strip()

            for frame in page.frames:
                try:
                    body = frame.locator("body[contenteditable='true']")
                    if body.count() > 0:
                        ph = body.get_attribute("data-placeholder") or ""
                        if "내용" in ph or "본문" in ph:
                            body.click(); body.type(plain, delay=15)
                            print(f"[4/5] 본문 입력 완료 ({len(plain)}자)")
                            break
                except Exception: continue
            page.wait_for_timeout(1000)

            try:
                tag_input = page.locator("input[placeholder*='태그']").first
                for tag in tags[:5]:
                    tag_input.type(tag, delay=30)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(300)
                print("    태그 입력 완료")
            except Exception:
                print("    태그 생략")

            print("[5/5] 발행...")
            for sel in ["button:has-text('발행')", ".publish_btn", "#publish"]:
                try:
                    page.click(sel, timeout=3000)
                    print("[5/5] 발행 완료")
                    break
                except Exception: continue

            page.wait_for_timeout(3000)
            print(f"[완료] {title}")
            return True

        except Exception as e:
            print(f"[실패] {e}")
            try: page.screenshot(path="error_screenshot.png")
            except Exception: pass
            return False
        finally:
            page.wait_for_timeout(2000)
            browser.close()
