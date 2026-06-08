# -*- coding: utf-8 -*-
"""
image_gen.py - DALL-E 3 이미지 생성 모듈
웹 최적화: 1024x1024 생성 → 800x800 PNG 저장
SEO 파일명: Claude API로 검색 최적화 파일명 생성
"""
import os, json, re, requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

def _get_seo_filenames_and_prompts(post_title, post_content, image_count, callback=None):
    """Claude API로 이미지별 SEO 파일명 + DALL-E 프롬프트 생성"""
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    if callback: callback(f"이미지 {image_count}개에 대한 SEO 파일명·프롬프트 생성 중...")

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        system="당신은 네이버 블로그 이미지 SEO 전문가입니다. JSON만 반환하세요.",
        messages=[{"role": "user", "content": f"""
블로그 제목: {post_title}
블로그 내용 요약: {post_content[:500]}

위 블로그에 삽입할 이미지 {image_count}개에 대해 아래를 생성해줘:

조건:
- 파일명: 네이버 검색 상위 노출을 위한 한글 키워드 중심, 하이픈 구분, 20자 이내
- DALL-E 프롬프트: 영문, 사실적이고 다양한 스타일 (도표/실사/인포그래픽/감성사진 등 섞기)
- 이미지 스타일: 매번 다양하게 (realistic photo / flat infographic / data chart / warm illustration 등)

JSON 형식으로만 반환:
{{
  "images": [
    {{
      "filename": "한글-키워드-파일명",
      "prompt": "English DALL-E prompt, photorealistic style, bright lighting",
      "style": "이미지 스타일 설명",
      "position": "글의 어느 위치에 삽입 (도입부/본론1/본론2/실천팁/마무리)"
    }}
  ]
}}
"""}]
    )

    raw = message.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)

def generate_images(post_title, post_content, save_dir, image_count=5, callback=None):
    """
    DALL-E 3로 이미지 생성 후 저장
    Returns: list of {filename, path, position, style}
    """
    from openai import OpenAI
    from PIL import Image
    import io

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        if callback: callback("[오류] OPENAI_API_KEY가 .env에 없습니다. 설정 탭에서 추가해주세요.")
        return []

    client = OpenAI(api_key=openai_key)
    Path(save_dir).mkdir(parents=True, exist_ok=True)

    # 1. SEO 파일명 + 프롬프트 생성
    meta = _get_seo_filenames_and_prompts(post_title, post_content, image_count, callback)
    images_meta = meta.get("images", [])[:image_count]

    results = []
    for i, img_info in enumerate(images_meta, 1):
        filename = img_info.get("filename", f"블로그이미지-{i}")
        # 파일명 안전화 (특수문자 제거)
        filename = re.sub(r'[^\w가-힣\-]', '', filename)
        filename = f"{filename}.png"
        save_path = os.path.join(save_dir, filename)

        prompt = img_info.get("prompt", "Educational content, clean modern design")
        style_hint = img_info.get("style", "")
        if callback: callback(f"이미지 {i}/{len(images_meta)} 생성 중... ({style_hint})")

        try:
            # DALL-E 3 생성
            response = client.images.generate(
                model="dall-e-3",
                prompt=f"{prompt}. High quality, sharp, web-optimized, professional blog image.",
                size="1024x1024",
                quality="standard",
                n=1
            )
            image_url = response.data[0].url

            # 다운로드 + 리사이즈 (800x800 웹 최적화)
            img_data = requests.get(image_url).content
            img = Image.open(io.BytesIO(img_data))
            img = img.resize((800, 800), Image.LANCZOS)
            img.save(save_path, "PNG", optimize=True)

            results.append({
                "filename": filename,
                "path": save_path,
                "position": img_info.get("position", f"본론{i}"),
                "style": style_hint
            })
            if callback: callback(f"  저장: {filename}")

        except Exception as e:
            if callback: callback(f"  이미지 {i} 오류: {e}")
            continue

    return results
