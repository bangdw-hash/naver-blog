# -*- coding: utf-8 -*-
"""
content_gen_v2.py - 다양한 인풋 기반 블로그 글 생성 (v2)
지원 인풋: 텍스트, YouTube URL, PDF, 이미지, 나의 생각
"""
import os, json, re
import anthropic
from dotenv import load_dotenv
load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def extract_pdf_text(filepath):
    """PDF에서 텍스트 추출"""
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t: text += t + "\n"
        return text[:3000]
    except ImportError:
        return "[pdfplumber 미설치 - pip install pdfplumber]"
    except Exception as e:
        return f"[PDF 읽기 오류: {e}]"


def search_youtube_url(keyword):
    """키워드로 유튜브 검색 URL 생성 (실제 검색 없이 URL 생성)"""
    import urllib.parse
    query = urllib.parse.quote(keyword)
    return f"https://www.youtube.com/results?search_query={query}"


def find_related_youtube(topic, callback=None):
    """Claude API로 관련 유튜브 검색 키워드 추천"""
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=300,
            messages=[{"role": "user", "content":
                f"'{topic}' 주제와 관련하여 유튜브에서 실제로 인기 있을 검색 키워드 3개를 JSON으로 반환해줘: {{\"keywords\": [\"키워드1\",\"키워드2\",\"키워드3\"]}}"}]
        )
        raw = msg.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"): raw = raw[4:]
        data = json.loads(raw.strip())
        keywords = data.get("keywords", [topic])
        return [{"keyword": k, "url": search_youtube_url(k)} for k in keywords[:3]]
    except Exception:
        return [{"keyword": topic, "url": search_youtube_url(topic)}]


def generate_blog_v2(
    raw_input_text: str,
    attached_files: list,     # [{type, name, content}]
    tone: str,                # "전문적" | "친근하게" | "감성적"
    include_youtube: bool,
    include_map: bool,
    image_count: int,
    blog_logic: str,
    concept: str,
    supplement: str = "",     # 보완 내용 (재생성 시)
    previous_content: str = "", # 이전 생성 내용
    callback=None
) -> dict:
    """
    다양한 인풋으로 블로그 글 생성
    Returns: {title, content, tags, youtube_links, image_positions, keyword}
    """
    if callback: callback("인풋 자료 분석 중...")

    # 파일 내용 합치기
    extra_content = ""
    for f in attached_files:
        if f["type"] == "pdf":
            extra_content += f"\n\n[첨부 PDF - {f['name']}]\n{f['content']}"
        elif f["type"] == "image":
            extra_content += f"\n\n[첨부 이미지 - {f['name']}] (이미지 내용을 참고하여 글 작성)"
        elif f["type"] == "text":
            extra_content += f"\n\n[첨부 파일 - {f['name']}]\n{f['content']}"

    # 유튜브 URL 찾기
    youtube_links = []
    if include_youtube:
        if callback: callback("관련 유튜브 링크 검색 중...")
        # 인풋에서 유튜브 URL 추출
        yt_urls = re.findall(r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+', raw_input_text)
        youtube_links = [{"url": u, "keyword": "입력된 URL"} for u in yt_urls]
        # 자동 검색도 추가
        if not yt_urls:
            topic_hint = raw_input_text[:50]
            youtube_links = find_related_youtube(topic_hint, callback)

    # 어투 지침
    tone_guide = {
        "전문적": "전문가적이고 신뢰감 있는 어투. 근거와 수치 중심. '~합니다' 체.",
        "친근하게": "따뜻하고 친근한 어투. 독자와 대화하듯. '~해요' 체. 이모지 1~2개.",
        "감성적": "공감을 이끌어내는 감성적 어투. 스토리텔링 방식. 독자의 마음에 호소."
    }.get(tone, "친근하게")

    # 보완 내용 반영 지시
    supplement_guide = ""
    if supplement and previous_content:
        supplement_guide = f"""
이전에 생성된 글:
{previous_content[:1000]}

사용자의 보완 요청:
{supplement}

위 보완 요청을 반드시 반영하여 새로 작성해줘.
"""

    # 유튜브 삽입 지침
    yt_guide = ""
    if youtube_links:
        yt_links_str = "\n".join([f"- {y['keyword']}: {y['url']}" for y in youtube_links])
        yt_guide = f"\n관련 유튜브 링크 (본문 적절한 위치에 삽입):\n{yt_links_str}"

    # 지도 삽입 지침
    map_guide = ""
    if include_map:
        map_guide = "\n※ 글에 장소/위치 정보가 있다면 네이버 지도 링크 형태로 삽입 표시: [지도:장소명]"

    if callback: callback("Claude AI로 블로그 글 생성 중...")

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4000,
        system=f"""당신은 네이버 블로그 상위 노출 전문 작가입니다.
블로그 컨셉: {concept}
어투 지침: {tone_guide}

[현재 적용 블로그 SEO 로직]
{blog_logic}

반드시 JSON 형식으로만 응답하세요.""",
        messages=[{"role": "user", "content": f"""
아래 자료를 바탕으로 네이버 블로그 글을 작성해줘.

[입력 자료]
{raw_input_text}
{extra_content}
{supplement_guide}
{yt_guide}
{map_guide}

[작성 조건]
1. 제목: 사람들이 가장 많이 검색할 키워드 중심, 클릭하고 싶은 제목 (20~28자)
   - 숫자 활용, 강한 이점 표현, 자극적이되 부정적이지 않게
2. 본문: 1800~2500자 (네이버 SEO 최적 길이)
3. 구성: 공감 도입 → 핵심 내용 3~4가지 (소제목 포함) → 실천 팁 → 마무리
4. 이미지 위치: 본문에 [이미지:{설명}] 형태로 {image_count}개 삽입 위치 표시
5. 인터넷에서 흔히 볼 수 없는 독창적이고 유용한 정보 중심
6. 검색 최적 키워드: 가장 검색량이 높을 핵심 키워드 1개 선정
7. 태그: 검색량 높은 태그 7개 (대표키워드 + 세부키워드 조합)
{'8. 유튜브 링크는 글 흐름상 자연스러운 위치에 삽입' if youtube_links else ''}
{'9. 장소 정보가 있으면 [지도:장소명] 형태로 표시' if include_map else ''}

JSON 형식으로만 반환:
{{
  "title": "제목",
  "content": "본문 (이미지 위치 [이미지:설명] 포함)",
  "tags": ["태그1","태그2","태그3","태그4","태그5","태그6","태그7"],
  "main_keyword": "핵심 검색 키워드",
  "youtube_links": {json.dumps([y['url'] for y in youtube_links], ensure_ascii=False)},
  "image_count": {image_count}
}}
"""}]
    )

    raw = message.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
        raw = raw.strip()

    result = json.loads(raw)
    result["youtube_links"] = youtube_links
    if callback: callback(f"글 생성 완료 - {result.get('title', '')}")
    return result
