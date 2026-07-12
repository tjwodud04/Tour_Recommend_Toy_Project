# constants.py — 도메인 상수 모음
#
# TourAPI 분류 코드, 지역 추정 힌트, 비추천(상업매장) 필터 등
# 코드 전반에서 재사용되는 도메인 데이터를 한곳에 모아 하드코딩을 제거한다.
from __future__ import annotations

import re
from typing import Final

# TourAPI 대분류(cat1) 후보 — LLM이 이 중 하나만 선택하도록 안내한다.
CAT1_CATEGORIES: Final[list[dict[str, str]]] = [
    {"code": "A01", "name": "자연"},
    {"code": "A02", "name": "인문(문화/예술/역사)"},
    {"code": "A03", "name": "레포츠"},
    {"code": "A04", "name": "쇼핑"},
    {"code": "A05", "name": "음식"},
    {"code": "B02", "name": "숙박"},
    {"code": "C01", "name": "추천코스"},
]

# 유효한 cat1 코드 집합(검증용)
CAT1_CODES: Final[frozenset[str]] = frozenset(c["code"] for c in CAT1_CATEGORIES)

# 지역명 추정 폴백 단어들(LLM 실패 시 질의에서 직접 탐색)
REGION_HINTS: Final[list[str]] = [
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남",
    "제주", "강원특별자치도", "제주특별자치도",
]

# areaCode2 지역명 정규화 시 제거할 접미사(예: '제주특별자치도' → '제주')
REGION_NAME_SUFFIXES: Final[tuple[str, ...]] = ("특별자치도", "광역시", "특별시")

# 상업매장 등 추천 목적에 맞지 않는 항목을 걸러내는 제목 패턴
STORE_FILTER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(대리점|지점|점$|마트|백화점|면세점|아울렛|할인점|스토어)"
)
