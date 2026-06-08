# naver_receipt.py - 네이버 영수증 리뷰 생성
import os, json, re
import anthropic
from dotenv import load_dotenv
load_dotenv()

def clean_markers(text: str) -> str:
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'---+', '', text)
    text = re.sub(r'^[-•]\s+', '', text, flags=re.MULTILINE)
    return text.strip()

def generate_receipt_review(
    place_name: str,
    place_addr: str,
    visit_date: str,
    menu_items: list,   # [{"name":"삼겹살", "price":15000}, ...]
    total_amount: int,
    rating_taste: int,
    rating_mood: int,
    memo: str,
    callback=None
) -> dict:
    """네이버 영수증 리뷰 텍스트 생성 (200-1000자 제한)"""

    ac = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    if callback: callback("영수증 리뷰 생성 중...")

    menu_str = ", ".join([f"{m['name']}({m.get('price', 0):,}원)" for m in menu_items]) if menu_items else "메뉴 미입력"
    star_taste = "★" * rating_taste + "☆" * (5 - rating_taste)

    prompt = f"""
네이버 영수증 리뷰를 작성해줘. 영수증 리뷰는 실제 방문 영수증 인증 후 작성하는 신뢰도 높은 리뷰야.

[영수증 정보]
음식점: {place_name}
주소: {place_addr}
방문일: {visit_date}
주문 메뉴: {menu_str}
결제 금액: {total_amount:,}원
맛 평점: {star_taste}
메모: {memo}

[작성 규칙]
1. 200-800자 사이로 작성 (영수증 리뷰 권장 분량)
2. 실제 영수증 기반 - 가격 대비 만족도 필수 포함
3. 주문한 메뉴 구체적 언급
4. 자연스러운 구어체 (마크다운 기호 절대 금지)
5. 재방문 의향 포함
6. 네이버 리뷰 형식 (짧고 명확하게)

JSON으로만 반환:
{{
  "review_text": "리뷰 본문 (200-800자)",
  "rating": {rating_taste},
  "keywords": ["키워드1", "키워드2", "키워드3"]
}}
"""

    msg = ac.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = msg.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
        raw = raw.split("```")[0]

    result = json.loads(raw.strip())
    result["review_text"] = clean_markers(result.get("review_text", ""))
    if callback: callback("영수증 리뷰 생성 완료!")
    return result
