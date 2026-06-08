# -*- coding: utf-8 -*-
"""
naver_place.py - 네이버 지역검색 API 래퍼
"""
import os, re, requests
from dotenv import load_dotenv
load_dotenv()

def _clean(text: str) -> str:
    """HTML 태그 제거"""
    return re.sub(r'<[^>]+>', '', text or '').strip()

def search_place(query: str, display: int = 5) -> list:
    """
    네이버 지역검색 API로 음식점 검색
    Returns: [{"title", "address", "road", "link", "mapx", "mapy", "category", "telephone"}]
    """
    client_id     = os.getenv("NAVER_CLIENT_ID", "")
    client_secret = os.getenv("NAVER_CLIENT_SECRET", "")

    if not client_id or client_id == "여기에입력" or not client_secret:
        # Mock 데이터 (API 키 없을 때)
        return [{
            "title":    query,
            "address":  "Seoul Gangnam-gu Teheran-ro 123",
            "road":     "Seoul Gangnam-gu Teheran-ro 123",
            "link":     "https://map.naver.com",
            "mapx":     "127.0276",
            "mapy":     "37.4979",
            "category": "Restaurant",
            "telephone":"02-0000-0000",
        }]

    url = "https://openapi.naver.com/v1/search/local.json"
    headers = {
        "X-Naver-Client-Id":     client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {"query": query, "display": display, "sort": "random"}

    try:
        res = requests.get(url, headers=headers, params=params, timeout=6)
        res.raise_for_status()
        items = res.json().get("items", [])
        return [{
            "title":    _clean(item.get("title", "")),
            "address":  item.get("address", ""),
            "road":     item.get("roadAddress", ""),
            "link":     item.get("link", ""),
            "mapx":     item.get("mapx", ""),
            "mapy":     item.get("mapy", ""),
            "category": item.get("category", ""),
            "telephone":item.get("telephone", ""),
        } for item in items]
    except Exception as e:
        return [{"error": str(e)}]
