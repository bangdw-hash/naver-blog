# -*- coding: utf-8 -*-
"""
food_gen.py - AI 맛집 탐방 블로그 글 생성 (Claude Haiku 사용 - 빠른 속도)
"""
import os, json, re
import anthropic
from dotenv import load_dotenv
load_dotenv()

def clean_markers(text: str) -> str:
    """AI 글쓰기 마커 제거"""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*',    r'\1', text)
    text = re.sub(r'#+\s*',        '',    text)
    text = re.sub(r'---+',         '',    text)
    text = re.sub(r'^[-•]\s+',     '',    text, flags=re.MULTILINE)
    return text.strip()

def _load_food_logic_guidelines() -> str:
    """food_logic.json 에서 SEO 가이드라인 로드 — 없으면 빈 문자열 반환"""
    try:
        from services.food_logic import load_food_logic
        logic = load_food_logic()
        if not logic or logic.get("version", 0) == 0:
            return ""
        parts = []
        if logic.get("guidelines"):
            parts.append("SEO 작성 가이드:\n" + logic["guidelines"])
        if logic.get("title_patterns"):
            parts.append("제목 패턴:\n" + logic["title_patterns"])
        if logic.get("hashtag_strategy"):
            parts.append("해시태그 전략:\n" + logic["hashtag_strategy"])
        if logic.get("forbidden"):
            parts.append("금지 표현:\n" + logic["forbidden"])
        return "\n\n".join(parts)
    except Exception:
        return ""


def generate_food_blog(
    place_name:   str,
    place_addr:   str,
    place_link:   str,
    place_cat:    str,
    visit_date:   str,
    rating_taste: int,
    rating_mood:  int,
    price_range:  str,
    revisit:      str,
    party_size:   str,
    memo:         str,
    photos:       list,
    callback=None
) -> dict:
    """맛집 탐방 블로그 글 생성"""

    ac = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    if callback: callback("맛집 블로그 글 생성 중...")

    star_taste  = "★" * rating_taste + "☆" * (5 - rating_taste)
    star_mood   = "★" * rating_mood  + "☆" * (5 - rating_mood)
    photo_count = len(photos)
    photo_desc  = f"사진 {photo_count}장 첨부됨" if photos else "사진 없음"

    # 저장된 맛집 SEO 로직 주입
    logic_block = _load_food_logic_guidelines()
    logic_section = f"\n[최신 SEO 작성 로직 - 반드시 반영]\n{logic_block}\n" if logic_block else ""

    prompt = f"""
다음 맛집 방문 정보로 블로그 글을 작성해줘.

[방문 정보]
음식점명: {place_name}
카테고리: {place_cat}
주소: {place_addr}
방문일: {visit_date}
동반 인원: {party_size}명
가격대: {price_range}
맛 평점: {star_taste} ({rating_taste}/5)
분위기: {star_mood} ({rating_mood}/5)
재방문 의향: {revisit}
메모: {memo}
{photo_desc}

[네이버 지도 링크]
{place_link}
{logic_section}
[작성 규칙 - 절대 준수]
1. 실제 방문한 사람이 쓴 자연스러운 후기 스타일
2. ** ## -- 등 마크다운 기호 절대 사용 금지
3. 단락을 자연스럽게 나눠 줄바꿈 사용
4. 별점과 느낌을 솔직하게 표현
5. 음식 맛, 분위기, 가격 순으로 자연스럽게 서술
6. 마지막에 #해시태그 형식으로 태그 5-8개
7. 500-700자 분량

JSON으로만 반환:
{{
  "title": "제목 (음식점명과 방문 후기 포함, 30자 이내)",
  "content": "본문 (줄바꿈 포함, 500-700자)",
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"],
  "main_keyword": "대표 키워드 1개"
}}
"""

    try:
        msg = ac.messages.create(
            model="claude-haiku-4-5",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = msg.content[0].text.strip()

        # JSON 추출
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"): raw = raw[4:]
            raw = raw.split("```")[0]

        result = json.loads(raw.strip())

        # AI 마커 제거
        result["content"] = clean_markers(result.get("content",""))
        result["title"]   = clean_markers(result.get("title",""))

        if callback: callback("글 생성 완료!")
        return result

    except json.JSONDecodeError as e:
        if callback: callback(f"JSON 파싱 오류: {e}")
        return {
            "title":        f"{place_name} 방문 후기",
            "content":      f"{place_name}에 다녀왔습니다.\n\n{memo}",
            "tags":         [place_name, place_cat, "맛집", "방문후기"],
            "main_keyword": place_name,
        }
    except Exception as e:
        if callback: callback(f"생성 오류: {e}")
        raise
