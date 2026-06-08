# food_logic.py - 맛집 블로그 최상위 노출 로직 학습 및 저장
import os, json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

FOOD_LOGIC_PATH = Path(os.path.dirname(__file__)) / ".." / "data" / "food_logic.json"

def load_food_logic() -> dict:
    if FOOD_LOGIC_PATH.exists():
        try:
            with open(FOOD_LOGIC_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"guidelines": "", "updated_at": None, "version": "0"}

def save_food_logic(data: dict):
    FOOD_LOGIC_PATH.parent.mkdir(exist_ok=True)
    with open(FOOD_LOGIC_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def update_food_logic(callback=None) -> dict:
    """Claude Sonnet으로 맛집 블로그 최상위 노출 로직 학습"""
    import anthropic
    ac = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    if callback: callback("맛집 블로그 최신 노출 패턴 분석 중...")

    prompt = """
네이버 블로그에서 맛집 탐방 글이 최상위 노출되기 위한 2025-2026년 최신 SEO 전략과 글쓰기 로직을 분석해줘.

다음 항목을 포함해서 상세하게 작성해줘:

1. 제목 작성법 (키워드 배치, 지역명+음식점명+특징 조합)
2. 도입부 작성 패턴 (방문 동기, 기대감 유발)
3. 본론 구성 (음식 설명, 분위기, 가격, 접근성)
4. 사진 배치 전략 (몇 장, 어떤 순서)
5. 해시태그 전략 (네이버 맛집 노출 최적 태그)
6. 마무리 작성법 (재방문 의향, 추천 대상)
7. 금지 표현 (AI 글 티 나는 표현들)
8. 최상위 노출 맛집 블로그들의 공통 패턴

실제 인기 맛집 블로그를 벤치마킹한 구체적인 가이드라인으로 작성해줘.
JSON으로만 반환:
{
  "guidelines": "상세 가이드라인 (2000자 이상)",
  "title_patterns": ["패턴1", "패턴2", "패턴3"],
  "forbidden": ["금지표현1", "금지표현2"],
  "hashtag_strategy": "해시태그 전략",
  "key_points": ["핵심1", "핵심2", "핵심3"]
}
"""

    if callback: callback("AI 분석 중... (30-60초 소요)")
    msg = ac.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = msg.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
        raw = raw.split("```")[0]

    result = json.loads(raw.strip())
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    result["updated_at"] = now
    result["version"] = str(int(load_food_logic().get("version", "0")) + 1)

    save_food_logic(result)
    if callback: callback(f"맛집 로직 업데이트 완료 ({now})")
    return result
