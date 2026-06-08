# -*- coding: utf-8 -*-
"""
image_gen.py - 이미지 생성 (한국 컨텍스트 특화 + SEO 메타데이터 임베드)
"""
import os, json, re, base64, requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

_working_model = None

def _detect_model(client):
    global _working_model
    if _working_model:
        return _working_model
    for model in ["gpt-image-1", "dall-e-3", "dall-e-2"]:
        try:
            r = client.images.generate(
                model=model, prompt="white circle", size="1024x1024", n=1
            )
            _working_model = model
            return model
        except Exception as e:
            msg = str(e)
            if "Billing hard limit" in msg or "billing" in msg.lower():
                raise RuntimeError(
                    "OpenAI 크레딧이 부족합니다.\n"
                    "https://platform.openai.com/settings/organization/billing 에서 충전해주세요."
                )
            continue
    raise RuntimeError("사용 가능한 OpenAI 이미지 모델이 없습니다.")


def _embed_png_metadata(img, title: str, keywords: list, description: str) -> object:
    """PNG 파일에 SEO 메타데이터 임베드 (검색 엔진 크롤링용)"""
    from PIL import PngImagePlugin
    meta = PngImagePlugin.PngInfo()
    meta.add_text("Title",       title[:100])
    meta.add_text("Keywords",    ", ".join(keywords[:10]))
    meta.add_text("Description", description[:300])
    meta.add_text("Author",      "N블로그자동화")
    meta.add_text("Software",    "NaverBlogAuto")
    return meta


def _get_image_prompts(post_title: str, post_content: str, image_count: int,
                       main_keyword: str, callback=None) -> dict:
    """Claude로 한국 컨텍스트 기반 이미지 프롬프트 생성"""
    import anthropic
    ac = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    if callback: callback(f"이미지 {image_count}개 프롬프트 생성 중...")

    msg = ac.messages.create(
        model="claude-haiku-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": f"""
블로그 제목: {post_title}
핵심 키워드: {main_keyword}
블로그 내용 요약: {post_content[:500]}

이 한국 교육 블로그에 삽입할 이미지 {image_count}개를 계획해줘.

[이미지 유형 - 다양하게 섞기]
- 실사형: 한국 초등학생들이 실제 공부하는 모습 (한국 교실, 한국 가정집 인테리어, 한국 학원 분위기)
- 다이어그램형: 핵심 개념을 시각화한 인포그래픽 (한글 텍스트 포함 불가, 도형과 화살표로만)
- 감성형: 따뜻한 한국 가정집에서 엄마와 아이가 함께 공부하는 장면
- 자료형: 수학 문제, 개념 정리 등 블로그 내용과 직결된 교육 자료 이미지

[중요 프롬프트 규칙]
- 모든 인물은 동아시아 외모, 한국인 특성 (Korean children, Korean parents, East Asian appearance)
- 배경은 한국 실내 (Korean home interior, Korean classroom, Korean study room)
- 밝고 따뜻한 조명, 사실적인 스타일
- 텍스트/글자는 프롬프트에 포함하지 말 것

JSON으로만 반환:
{{
  "images": [
    {{
      "filename": "한글-키워드-하이픈구분-20자이내",
      "prompt": "detailed English DALL-E prompt with Korean context",
      "type": "실사형/다이어그램형/감성형/자료형 중 하나",
      "seo_description": "이미지 설명 (한글 50자)",
      "position": "도입부/본론1/본론2/실천팁/마무리 중 하나"
    }}
  ]
}}
"""}]
    )
    raw = msg.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
    return json.loads(raw.strip())


def generate_images(post_title, post_content, save_dir, image_count=5,
                    main_keyword="", tags=None, callback=None):
    """이미지 생성 + 저장 + SEO 메타데이터 임베드"""
    from openai import OpenAI
    from PIL import Image
    import io

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key or openai_key == "여기에입력":
        if callback: callback("오류: OPENAI_API_KEY가 설정되지 않았습니다.")
        return []

    oc = OpenAI(api_key=openai_key)
    Path(save_dir).mkdir(parents=True, exist_ok=True)

    # 모델 탐지
    try:
        if callback: callback("OpenAI 이미지 API 확인 중...")
        model = _detect_model(oc)
        if callback: callback(f"모델 사용: {model}")
    except RuntimeError as e:
        if callback: callback(f"오류: {e}")
        return []

    # 프롬프트 생성
    try:
        meta_data = _get_image_prompts(post_title, post_content, image_count, main_keyword, callback)
        images_meta = meta_data.get("images", [])[:image_count]
    except Exception as e:
        if callback: callback(f"프롬프트 생성 오류: {e}")
        images_meta = [{
            "filename": f"한국교육이미지-{i}",
            "prompt":   f"Korean elementary school children studying together in a bright Korean classroom, realistic photo style, warm lighting, East Asian appearance, index {i}",
            "type":     "실사형",
            "seo_description": f"{post_title} 관련 이미지",
            "position": "본론"
        } for i in range(1, image_count+1)]

    # 키워드 목록
    keyword_list = [main_keyword] + (tags[:5] if tags else [])

    results = []
    for i, img_info in enumerate(images_meta, 1):
        raw_name  = img_info.get("filename", f"이미지-{i}")
        safe_name = re.sub(r'[^\w가-힣\-]', '', raw_name) or f"image-{i}"
        filename  = f"{safe_name}.png"
        save_path = os.path.join(save_dir, filename)

        prompt     = img_info.get("prompt", "Korean children studying, warm classroom")
        img_type   = img_info.get("type",   "실사형")
        seo_desc   = img_info.get("seo_description", post_title)

        # 타입별 프롬프트 강화
        type_suffix = {
            "실사형":    "photorealistic, Canon DSLR quality, natural lighting, Korean home or classroom interior",
            "다이어그램형": "clean infographic diagram, flat design, colorful arrows and shapes, white background, no text",
            "감성형":    "warm and cozy atmosphere, soft bokeh, golden hour lighting, Korean family home",
            "자료형":    "educational material, clean layout, geometric shapes, minimal design, bright colors",
        }.get(img_type, "photorealistic, bright, professional")

        full_prompt = (
            f"{prompt}. {type_suffix}. "
            f"Korean context, East Asian children or parents, "
            f"high quality, web-optimized, professional blog image."
        )

        if callback: callback(f"이미지 {i}/{len(images_meta)} 생성 중... [{img_type}]")

        try:
            kwargs = dict(model=model, prompt=full_prompt, size="1024x1024", n=1)
            if model == "dall-e-3":
                kwargs["quality"] = "standard"

            response = oc.images.generate(**kwargs)
            item = response.data[0]

            # 이미지 데이터 가져오기
            b64 = getattr(item, 'b64_json', None)
            if b64:
                img_data = base64.b64decode(b64)
            else:
                url = getattr(item, 'url', None)
                if not url:
                    raise ValueError("이미지 데이터 없음")
                img_data = requests.get(url, timeout=30).content

            # 리사이즈
            img = Image.open(io.BytesIO(img_data)).convert("RGBA")
            img = img.resize((800, 800), Image.LANCZOS)

            # PNG SEO 메타데이터 임베드
            png_meta = _embed_png_metadata(
                img,
                title=f"{post_title} - {seo_desc}",
                keywords=keyword_list,
                description=seo_desc
            )

            # RGBA → RGB 변환 후 저장
            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
            rgb_img.save(save_path, "PNG", optimize=True, pnginfo=png_meta)

            results.append({
                "filename":    filename,
                "path":        save_path,
                "position":    img_info.get("position", f"본론{i}"),
                "type":        img_type,
                "description": seo_desc
            })
            if callback: callback(f"저장: {filename}")

        except Exception as e:
            err = str(e)
            if "Billing hard limit" in err or "billing" in err.lower():
                if callback: callback("OpenAI 크레딧 부족 — billing 페이지에서 충전 필요")
                break
            if callback: callback(f"이미지 {i} 오류: {err[:120]}")
            continue

    return results
