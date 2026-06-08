# -*- coding: utf-8 -*-
"""
content_gen_v2.py - 다양한 인풋 기반 블로그 글 생성 (v2)
최적화: 재생성 시 벤치마킹/유튜브 건너뜀, 첫 생성 시 병렬 처리
"""
import os, json, re, threading
import anthropic
from dotenv import load_dotenv
load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ── 캐시 (메모리 + 디스크, Flask 재시작 후에도 유지) ────────
import pathlib as _pl

_CACHE_FILE = _pl.Path("data/gen_cache.json")
_benchmark_cache: dict = {}
_youtube_cache:   dict = {}

def _load_cache():
    global _benchmark_cache, _youtube_cache
    try:
        if _CACHE_FILE.exists():
            d = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            _benchmark_cache = d.get("benchmark", {})
            _youtube_cache   = d.get("youtube",   {})
    except Exception:
        pass

def _save_cache():
    try:
        _CACHE_FILE.parent.mkdir(exist_ok=True)
        _CACHE_FILE.write_text(
            json.dumps({"benchmark": _benchmark_cache, "youtube": _youtube_cache}, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception:
        pass

_load_cache()  # 모듈 로드 시 디스크에서 복원


def _cache_key(text: str) -> str:
    return text.strip()[:60].lower()


# ── AI 마커 완전 제거 후처리 ─────────────────────────────────
def clean_ai_markers(text: str) -> str:
    if not text:
        return text

    protected = {}
    def protect(m):
        key = f"__IMG{len(protected)}__"
        protected[key] = m.group(0)
        return key
    text = re.sub(r'\[이미지:[^\]]*\]', protect, text)
    text = re.sub(r'\[지도:[^\]]*\]',   protect, text)

    text = re.sub(r'^#{1,6}\s*(.+)$',      r'\1',  text, flags=re.MULTILINE)
    text = re.sub(r'\*{2,3}([^*]+)\*{2,3}', r'\1', text)
    text = re.sub(r'_{2,3}([^_]+)_{2,3}',   r'\1', text)
    text = re.sub(r'\*([^*\n]+)\*',          r'\1', text)
    text = re.sub(r'_([^_\n]+)_',            r'\1', text)
    text = re.sub(r'^[-*_]{2,}\s*$',         '',    text, flags=re.MULTILINE)
    text = re.sub(r'^[\-\*\•]\s+(.+)$',      r'\1', text, flags=re.MULTILINE)
    text = re.sub(r'^>\s*(.+)$',             r'\1', text, flags=re.MULTILINE)
    text = re.sub(r'```[\s\S]*?```',         '',    text)
    text = re.sub(r'`([^`]+)`',              r'\1', text)
    text = re.sub(r'\n{3,}',               '\n\n',  text)

    for key, val in protected.items():
        text = text.replace(key, val)
    return text.strip()


# ── 인기 글 패턴 벤치마킹 (캐싱) ────────────────────────────
def benchmark_popular_style(topic: str, concept: str) -> str:
    key = _cache_key(topic)
    if key in _benchmark_cache:
        return _benchmark_cache[key]
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=600,
            messages=[{"role": "user", "content": f"""
네이버 블로그에서 '{topic}' 주제로 조회수·공감 높은 인기 글들의 공통 특징을 분석해줘.
블로그 컨셉: {concept}

1. 도입부 첫 문장 패턴 (예시 2가지)
2. 소제목 처리 방식 (기호 없이)
3. 자주 쓰는 구어체 표현 5가지
4. 독자 공감 유발 방식
5. 마무리 패턴

간결하게만 답해줘.
"""}]
        )
        result = msg.content[0].text.strip()
        _benchmark_cache[key] = result
        _save_cache()
        return result
    except Exception:
        return ""


# ── 유튜브 URL (캐싱) ────────────────────────────────────────
def search_youtube_url(keyword):
    import urllib.parse
    return f"https://www.youtube.com/results?search_query={urllib.parse.quote(keyword)}"


def find_related_youtube(topic, callback=None):
    key = _cache_key(topic)
    if key in _youtube_cache:
        return _youtube_cache[key]
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=200,
            messages=[{"role": "user", "content":
                f"'{topic}' 유튜브 인기 검색 키워드 3개를 JSON으로: {{\"keywords\": [\"키워드1\",\"키워드2\",\"키워드3\"]}}"}]
        )
        raw = msg.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"): raw = raw[4:]
        data = json.loads(raw.strip())
        keywords = data.get("keywords", [topic])
        result = [{"keyword": k, "url": search_youtube_url(k)} for k in keywords[:3]]
        _youtube_cache[key] = result
        _save_cache()
        return result
    except Exception:
        return [{"keyword": topic, "url": search_youtube_url(topic)}]


# ── PDF 텍스트 추출 ──────────────────────────────────────────
def extract_pdf_text(filepath):
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t: text += t + "\n"
        return text[:3000]
    except ImportError:
        return "[pdfplumber 미설치]"
    except Exception as e:
        return f"[PDF 읽기 오류: {e}]"


# ── 메인 생성 ────────────────────────────────────────────────
def generate_blog_v2(
    raw_input_text: str,
    attached_files: list,
    tone: str,
    include_youtube: bool,
    include_map: bool,
    image_count: int,
    blog_logic: str,
    concept: str,
    supplement: str = "",
    previous_content: str = "",
    callback=None
) -> dict:

    is_regeneration = bool(supplement and previous_content)

    if callback: callback("인풋 자료 분석 중...")

    # 파일 내용
    extra_content = ""
    for f in attached_files:
        if f["type"] == "pdf":
            extra_content += f"\n\n[첨부 PDF - {f['name']}]\n{f['content']}"
        elif f["type"] == "image":
            extra_content += f"\n\n[첨부 이미지 - {f['name']}]"
        elif f["type"] == "text":
            extra_content += f"\n\n[첨부 파일 - {f['name']}]\n{f['content']}"

    # ── 재생성: 캐시 재사용 & 전처리 건너뜀 ────────────────
    if is_regeneration:
        if callback: callback("보완 내용 반영 중...")
        topic_hint = raw_input_text[:60]
        popular_style = _benchmark_cache.get(_cache_key(topic_hint), "")
        youtube_links = _youtube_cache.get(_cache_key(topic_hint), [])
        # 유튜브 URL이 없어도 입력에서 추출
        if not youtube_links and include_youtube:
            yt_urls = re.findall(r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+', raw_input_text)
            youtube_links = [{"url": u, "keyword": "입력된 URL"} for u in yt_urls]

    # ── 첫 생성: 벤치마킹 + 유튜브 병렬 실행 ──────────────
    else:
        topic_hint = raw_input_text[:60]
        popular_style = ""
        youtube_links = []

        results = {}
        errors  = {}

        def _bench():
            try:
                if callback: callback("인기 글 패턴 분석 중...")
                results["style"] = benchmark_popular_style(topic_hint, concept)
            except Exception as e:
                errors["bench"] = str(e)

        def _yt():
            try:
                if include_youtube:
                    yt_urls = re.findall(r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+', raw_input_text)
                    if yt_urls:
                        results["yt"] = [{"url": u, "keyword": "입력된 URL"} for u in yt_urls]
                    else:
                        if callback: callback("관련 유튜브 링크 검색 중...")
                        results["yt"] = find_related_youtube(topic_hint)
            except Exception as e:
                errors["yt"] = str(e)

        t1 = threading.Thread(target=_bench, daemon=True)
        t2 = threading.Thread(target=_yt,   daemon=True)
        t1.start(); t2.start()
        t1.join();  t2.join()

        popular_style = results.get("style", "")
        youtube_links = results.get("yt",    [])

    # 어투 설정
    _tone_presets = {
        "전문적":  {
            "desc":   "전문가 신뢰감. 근거·수치 중심. '~합니다' 체.",
            "opener": "수치·팩트로 시작. '실제로', '연구에 따르면' 활용.",
            "style":  "짧고 강한 문장. 소제목은 독립 행으로."
        },
        "친근하게": {
            "desc":   "동네 언니·오빠처럼 편하게. '~해요' 체.",
            "opener": "'혹시 이런 경험 있으세요?', '저도 처음엔' 식 공감 시작.",
            "style":  "짧은 문장 + 행간 여유. '그래서', '근데', '사실' 구어 연결어 활용."
        },
        "감성적":  {
            "desc":   "따뜻한 감성 스토리텔링. 독자 마음에 호소. '~해요' 체.",
            "opener": "작은 일상 에피소드나 감정 묘사로 시작.",
            "style":  "여백 있는 문단. 비유와 이미지 묘사 풍부하게."
        }
    }
    tone_map = _tone_presets.get(tone, _tone_presets["친근하게"])

    # 보완 지시 (재생성)
    supplement_guide = ""
    if is_regeneration:
        supplement_guide = f"""
[이전 글 일부]
{previous_content[:600]}

[보완 요청]
{supplement}

위 보완을 반드시 반영하여 새로 작성해줘.
"""

    yt_guide = ""
    if youtube_links:
        yt_guide = "\n관련 유튜브 링크 (본문 자연스러운 위치에 삽입):\n" + \
                   "\n".join(f"- {y['keyword']}: {y['url']}" for y in youtube_links)

    map_guide = "\n장소 정보가 있으면 [지도:장소명] 형태로 표시해줘." if include_map else ""

    if callback:
        callback("보완 내용 반영해서 재작성 중..." if is_regeneration else "Claude AI로 블로그 글 작성 중...")

    system_prompt = f"""당신은 네이버 블로그에서 조회수 1만 이상을 꾸준히 받는 인기 블로거입니다.
블로그 컨셉: {concept}
어투: {tone_map['desc']}
도입: {tone_map['opener']}
문체: {tone_map['style']}

{f"[이 주제 인기 글 패턴]{chr(10)}{popular_style}" if popular_style else ""}

[현재 네이버 SEO 로직]
{blog_logic[:500] if blog_logic else '기본 SEO 적용'}

━━━━━━━━━━━━━━━━━━━━━━━━━━
[절대 금지]
· **굵은글씨** 기호 사용 금지
· ## 소제목 형식 금지
· --- 구분선 금지
· - 항목 리스트 형식 금지
· * 기울임 금지
· 기계적 나열 ("첫째, 둘째") 금지
· 보고서·문어체 금지

[소제목 처리]
자연스러운 질문·감탄 형식의 독립 행:
예) "그런데 왜 이 방법이 효과가 있을까요?"
예) "직접 해보니 달랐어요"

반드시 JSON으로만 응답."""

    user_prompt = f"""아래 자료로 실제 인간이 쓴 것처럼 자연스러운 네이버 블로그 글을 써줘.

[입력 자료]
{raw_input_text}
{extra_content}
{supplement_guide}
{yt_guide}
{map_guide}

[요건]
1. 제목: 검색 키워드 포함, 클릭하고 싶은 20~28자
2. 본문: 1800~2500자, 실제 경험·공감 중심
3. 구성: 공감 도입 → 핵심 3~4가지 → 실용 팁 → 마무리
4. 이미지 자리: [이미지:{{설명}}] 형태로 {image_count}곳 삽입
5. 핵심 검색 키워드 1개
6. 태그 7개
{'7. 유튜브 링크 본문에 자연스럽게 녹여서 삽입' if youtube_links else ''}

JSON으로만 반환:
{{
  "title": "제목",
  "content": "본문 전체 (마크다운 기호 없이 순수 텍스트)",
  "tags": ["태그1","태그2","태그3","태그4","태그5","태그6","태그7"],
  "main_keyword": "핵심 키워드",
  "youtube_links": {json.dumps([y['url'] for y in youtube_links], ensure_ascii=False)},
  "image_count": {image_count}
}}"""

    # 재생성은 Haiku(빠름), 첫 생성은 Sonnet(고품질)
    model  = "claude-haiku-4-5"    if is_regeneration else "claude-sonnet-4-5"
    tokens = 4000                  if is_regeneration else 6000

    message = client.messages.create(
        model=model,
        max_tokens=tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )

    raw = message.content[0].text.strip()
    # JSON 블록 추출
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
        raw = raw.strip()

    # JSON 잘림 복구: 마지막 } 까지만 사용
    if not raw.endswith("}"):
        last_brace = raw.rfind("}")
        if last_brace != -1:
            raw = raw[:last_brace+1]

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # content 필드만 깨진 경우 최소 복구
        title_m   = re.search(r'"title"\s*:\s*"([^"]+)"',   raw)
        keyword_m = re.search(r'"main_keyword"\s*:\s*"([^"]+)"', raw)
        # content는 끝이 잘렸을 수 있으므로 끝부분 닫기
        content_m = re.search(r'"content"\s*:\s*"([\s\S]+)', raw)
        content_raw = content_m.group(1) if content_m else ""
        # 잘린 content 정리 (마지막 불완전 문장 제거)
        if content_raw:
            for stop in ['",', '"', '\n']:
                idx = content_raw.rfind(stop)
                if idx > len(content_raw) // 2:
                    content_raw = content_raw[:idx]
                    break
        tags_m = re.findall(r'"([^"]{2,20})"', raw[raw.find('"tags"'):raw.find('"tags"')+200] if '"tags"' in raw else "")
        result = {
            "title":        title_m.group(1)   if title_m   else "제목 생성 오류 - 재시도해주세요",
            "content":      content_raw.replace('\\n', '\n').replace('\\"', '"'),
            "tags":         tags_m[:7] if tags_m else [],
            "main_keyword": keyword_m.group(1) if keyword_m else "",
        }

    if callback: callback("AI 표현 정제 중...")
    result["content"] = clean_ai_markers(result.get("content", ""))
    result["title"]   = clean_ai_markers(result.get("title",   ""))

    result["youtube_links"] = youtube_links
    if callback: callback(f"생성 완료 — {result.get('title', '')}")
    return result
