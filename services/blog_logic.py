# -*- coding: utf-8 -*-
"""
blog_logic.py - 네이버 블로그 작성 로직 관리
[블로그 로직 최신화] 버튼 클릭 시 Claude API로 최신 가이드라인 업데이트
"""
import json, os
from datetime import datetime
import anthropic
from dotenv import load_dotenv
load_dotenv()

LOGIC_FILE = "blog_logic.json"

DEFAULT_LOGIC = {
    "updated_at": "기본값 (최신화 필요)",
    "version": "0.0",
    "guidelines": """
[네이버 블로그 SEO 기본 지침]
1. 제목: 15~25자, 핵심 키워드 포함, 숫자/감성어 활용
2. 본문 길이: 1500~3000자 (저품질 방지)
3. 이미지: 최소 3~5장, 본문 사이 자연스럽게 배치
4. 단락: 3~4문장씩 끊기, 가독성 우선
5. 소제목: 2~3개 이상 (볼드 또는 구분선)
6. 키워드: 제목·첫문단·소제목·마지막 문단에 자연스럽게 배치
7. 태그: 5~10개, 실제 검색어 중심
8. 저품질 회피: 복붙 금지, 광고성 링크 최소화
"""
}

def load_blog_logic():
    if os.path.exists(LOGIC_FILE):
        with open(LOGIC_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_LOGIC.copy()

def save_blog_logic(data):
    with open(LOGIC_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def update_blog_logic(callback=None):
    """
    Claude API로 최신 네이버 블로그 SEO 가이드라인 업데이트
    callback(status_msg) 으로 진행 상태 전달
    """
    try:
        if callback: callback("Claude API에 최신 블로그 로직 요청 중...")
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=3000,
            system="당신은 네이버 블로그 SEO 전문가입니다. 실제 상위 노출 블로그 패턴을 분석하여 구체적 지침을 제공합니다.",
            messages=[{"role": "user", "content": """
2024~2025년 기준 네이버 블로그 검색 상위 노출 최적화 방법론을 실전 전문가 수준으로 정리해줘.
인기 블로그들의 공통 패턴을 분석한 결과를 포함해서 아래 항목을 상세히 작성해줘:

1. 제목 작성 공식 (클릭률 높이는 패턴 예시 5가지 포함)
2. 본문 최적 길이 및 단락 구조
3. 이미지 활용 전략 (수량, 배치 위치, SEO 파일명 공식)
4. 키워드 배치 전략 (제목/첫문단/소제목/마지막 비율)
5. 태그 선택 기준 (대분류 + 세부 키워드 조합법)
6. 어투별 특징 (전문적 / 친근하게 / 감성적 - 각 예시 포함)
7. 네이버 저품질 필터 회피 핵심 원칙
8. 현재 인기 교육 블로그들의 공통 구성 패턴
9. 이미지 파일명 SEO 최적화 공식

위 내용을 실제 블로그 작성에 즉시 적용할 수 있도록 구체적으로 작성해줘.
"""}]
        )

        guidelines = message.content[0].text
        data = {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "version": datetime.now().strftime("%Y%m%d"),
            "guidelines": guidelines
        }
        save_blog_logic(data)
        if callback: callback(f"블로그 로직 최신화 완료! ({data['updated_at']})")
        return data

    except Exception as e:
        if callback: callback(f"오류: {e}")
        return None
