# recommender.py — 추천 로직(피처/추천 계층)
#
# 흐름: (질의) → LLM으로 지역/대분류 추출 → TourAPI 목록/상세 조회
#       → 이미지 선택 + 한 줄 요약 → 카드 N개 생성.
# 외부 I/O는 LLMClient / TourApiClient / image_service에 위임한다.
from __future__ import annotations

import json
import random
import re
from typing import Any, Optional

from config import Config
from constants import CAT1_CATEGORIES, CAT1_CODES, REGION_HINTS, STORE_FILTER_PATTERN
from image_service import ImageUrlCache, to_https, validate_image_url
from llm_client import LLMClient
from tour_api_client import TourApiClient

# 추천 카드 타입 별칭
Card = dict[str, Any]


def _compose_full_address(addr1: str, addr2: str) -> str:
    """addr1/addr2를 공백으로 결합한다."""
    a1, a2 = (addr1 or "").strip(), (addr2 or "").strip()
    return f"{a1} {a2}".strip() if a1 and a2 else (a1 or a2 or "")


def _first_sentence(text: str) -> str:
    """문장 구분자(., !, ?, 。) 기준 첫 문장을 반환한다."""
    return re.split(r"[.!?。]\s*", text)[0].strip()


class RecommendationService:
    """지역/대분류 추출 → TourAPI 조회 → 요약/이미지 → 카드 생성."""

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        api_client: Optional[TourApiClient] = None,
    ) -> None:
        self.llm = llm or LLMClient()
        self.api = api_client or TourApiClient()
        self._img_cache = ImageUrlCache(Config.IMAGE_CACHE_TTL_SEC, Config.IMAGE_CACHE_MAX)

    # ---------- 1) (region, cat1) 추출 ----------
    def _region_fallback(self, user_query: str) -> str:
        """LLM 실패 시 질의에서 지역 힌트를 직접 탐색(없으면 질의 원문)."""
        text = (user_query or "").strip()
        return next((word for word in REGION_HINTS if word in text), text)

    def _extract_region_and_cat1(self, user_query: str) -> tuple[str, Optional[str]]:
        """LLM으로 지역 1개 + cat1 코드 1개를 추출한다(실패 시 지역 폴백)."""
        try:
            cat_list = "\n".join(f"- {c['code']} : {c['name']}" for c in CAT1_CATEGORIES)
            prompt = f"""
다음 한국어 요청에서
1) 지역명 1개(예: 제주, 부산, 강릉)와
2) 아래 목록 중 가장 가까운 대분류 cat1 코드 1개
를 JSON으로만 출력하세요.

대분류 목록:
{cat_list}

출력 스키마:
{{"region":"제주","cat1":"A01"}}

요청: {user_query}
""".strip()
            content = self.llm.complete_chat(
                messages=[
                    {"role": "system", "content": "반드시 유효한 JSON만 출력하세요."},
                    {"role": "user", "content": prompt},
                ],
                temperature=Config.EXTRACT_TEMPERATURE,
                max_tokens=Config.EXTRACT_MAX_TOKENS,
                response_format={"type": "json_object"},
            )
            data = json.loads(content or "{}")
            region = (data.get("region") or "").strip()
            cat1 = (data.get("cat1") or "").strip().upper()
            if cat1 not in CAT1_CODES:
                cat1 = None
            if not region:
                region = self._region_fallback(user_query)
            return region, cat1
        except Exception:
            return self._region_fallback(user_query), None

    # ---------- 2) 한 줄 요약 ----------
    def _summarize_one_line(self, text: str) -> str:
        """overview를 한국어 1문장으로 요약한다(실패 시 원문 절단 폴백)."""
        source = (text or "").strip()
        if not source:
            return ""
        try:
            system_msg = (
                "한국어 문장 하나로만 답해. 금지어: 요약,정리,한줄,한 문장. "
                f"{Config.SUMMARY_MIN_CHARS}~{Config.SUMMARY_MAX_CHARS}자."
            )
            content = self.llm.complete_chat(
                messages=[
                    {"role": "system", "content": system_msg},
                    {
                        "role": "user",
                        "content": (
                            "예시입력: 천지연폭포는 계곡과 숲길이 아름답다.\n"
                            "예시출력: 숲길과 어우러진 천지연폭포의 경치를 즐길 수 있다.\n\n"
                            f"다음 글을 같은 형식으로 요약:\n{source}"
                        ),
                    },
                ],
                temperature=Config.SUMMARY_TEMPERATURE,
                max_tokens=Config.SUMMARY_MAX_TOKENS,
            )
            sentence = _first_sentence(content or "")
            return (sentence + ".") if sentence else ""
        except Exception:
            sentence = _first_sentence(source)
            limit = Config.SUMMARY_FALLBACK_LEN
            return sentence[:limit] + ("..." if len(sentence) > limit else "")

    # ---------- 3) 목록 정리 ----------
    @staticmethod
    def _clean_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """제목이 없거나 상업매장으로 보이는 항목을 걸러낸다."""
        cleaned = []
        for item in items:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            if STORE_FILTER_PATTERN.search(title):
                continue
            cleaned.append(item)
        return cleaned

    # ---------- 4) 이미지 선택 ----------
    def _pick_valid_image(self, content_id: str, firstimage2: str, firstimage: str) -> str:
        """캐시 → firstimage2 → firstimage → detailImage2 순으로 유효 이미지를 고른다."""
        cached = self._img_cache.get(content_id)
        if cached:
            return cached
        for raw in (firstimage2, firstimage):
            valid = validate_image_url(raw)
            if valid:
                self._img_cache.set(content_id, valid)
                return valid
        image = self.api.fetch_detail_image(content_id)
        if image:
            self._img_cache.set(content_id, image)
        return image

    # ---------- 메인 ----------
    def recommend(self, user_query: str, want: Optional[int] = None) -> list[Card]:
        """사용자 질의 → (지역/분류) → 목록 → 상세/요약 → 카드 N개 생성."""
        want = want or Config.NUM_RECOMMEND

        # 1) 지역/대분류 추출 및 지역코드 해석
        region, cat1 = self._extract_region_and_cat1(user_query)
        area_code, sigungu_code = self.api.resolve_area_code(region)

        # 2) 지역 기반 목록 조회(후보를 넉넉히 확보)
        num_rows = max(Config.MIN_LIST_ROWS, want * Config.API_FETCH_MULTIPLIER)
        items = self.api.fetch_area_based_list(
            num_rows=num_rows,
            area_code=area_code,
            sigungu_code=sigungu_code,
            cat1=cat1,
        )

        # 3) 휴리스틱 클린
        items = self._clean_items(items)
        if not items:
            return []

        # 4) 샘플링
        sample = random.sample(items, k=min(want, len(items)))

        # 5) 상세/요약/이미지 후 카드화
        cards: list[Card] = []
        for item in sample:
            content_id = (item.get("contentid") or "").strip()
            title = (item.get("title") or "").replace("<b>", "").replace("</b>", "").strip()
            address = _compose_full_address(item.get("addr1") or "", item.get("addr2") or "")

            overview, homepage = self.api.fetch_detail_common(content_id)
            reason = self._summarize_one_line(overview) or (
                overview[: Config.OVERVIEW_FALLBACK_LEN] + "..." if overview else ""
            )

            image_url = self._pick_valid_image(
                content_id,
                to_https(item.get("firstimage2") or ""),
                to_https(item.get("firstimage") or ""),
            )

            cards.append(
                {
                    "name": title or "이름 정보 없음",
                    "reason": reason or "한 줄 설명 없음",
                    "address": address or "주소 정보 없음",
                    "image_url": image_url,
                    "homepage": homepage,
                    "metadata": {
                        "contentid": content_id,
                        "cat1": item.get("cat1") or "",
                        "addr1": item.get("addr1") or "",
                        "firstimage2": item.get("firstimage2") or "",
                        "title": title,
                        "region": region,
                    },
                }
            )

        # 6) 정확히 want개까지 반환(부족 시 있는 만큼)
        return cards[:want]
