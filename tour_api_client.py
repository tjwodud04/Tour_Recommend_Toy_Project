# tour_api_client.py — 한국관광공사 TourAPI HTTP 클라이언트
#
# 순수 데이터 계층: 엔드포인트 호출과 JSON 파싱만 담당한다.
# 추천/요약 등 도메인 로직은 recommender.py가 담당한다.
from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import unquote

import requests

from config import Config
from constants import REGION_NAME_SUFFIXES
from image_service import to_https, validate_image_url


def normalize_homepage(raw: str) -> str:
    """detailCommon2의 homepage 필드를 절대 URL로 정규화한다.

    HTML ``a`` 태그가 섞여 오는 경우가 많아 href를 추출하고,
    HTML 엔티티/스킴을 보정한 뒤 https로 승격한다.
    """
    text = (raw or "").strip()
    if not text:
        return ""
    match = re.search(r'href=["\']([^"\']+)["\']', text, re.I)  # a 태그 내부 링크 추출
    if match:
        text = match.group(1).strip()
    text = text.replace("&amp;", "&")                           # HTML 엔티티 정리
    if text.startswith("//"):
        text = "https:" + text                                  # 스킴 보정
    if not re.match(r"^https?://", text, re.I):
        text = "https://" + text
    return to_https(text)


class TourApiClient:
    """TourAPI(KorService2) 엔드포인트 호출 래퍼."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self.base_url = base_url or Config.KOREA_TOURISM_API_BASE
        self.api_key = api_key or Config.KOREA_TOURISM_API_KEY
        self.timeout = timeout or Config.TIMEOUT

    # ---------- 공용 유틸 ----------
    def _service_key(self) -> str:
        """인코딩 키가 와도 안전하게 사용(퍼센트 디코드 + 공백 제거)."""
        key = (self.api_key or "").strip()
        if "%" in key:
            key = unquote(key)
        return key.replace(" ", "")

    def _base_params(self) -> dict[str, Any]:
        """모든 호출에 공통으로 들어가는 파라미터."""
        return {
            "serviceKey": self._service_key(),
            "MobileOS": Config.TOURAPI_MOBILE_OS,
            "MobileApp": Config.TOURAPI_MOBILE_APP,
            "_type": Config.TOURAPI_RESPONSE_TYPE,
        }

    @staticmethod
    def _safe_json(resp: requests.Response) -> dict[str, Any]:
        """JSON 응답만 파싱한다(아니면 본문 앞부분을 담아 에러)."""
        content_type = (resp.headers.get("Content-Type") or "").lower()
        text = (resp.text or "").strip()
        if "json" in content_type or (text and (text.startswith("{") or text.startswith("["))):
            try:
                return resp.json()
            except Exception:
                pass
        head = text[: Config.BODY_PREVIEW_LEN].replace("\n", " ") if text else ""
        raise ValueError(
            f"Non-JSON response (status={resp.status_code}, ct='{content_type}'). Body head: {head}"
        )

    @classmethod
    def _extract_items(cls, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """``response.body.items.item``을 항상 리스트로 정규화해 반환한다."""
        items = (
            payload.get("response", {})
            .get("body", {})
            .get("items", {})
            .get("item", [])
        ) or []
        if isinstance(items, dict):
            return [items]
        if not isinstance(items, list):
            return [items]
        return items

    def _get(self, endpoint: str, extra_params: dict[str, Any]) -> dict[str, Any]:
        """엔드포인트 GET 호출 후 JSON 파싱 결과를 반환한다."""
        url = f"{self.base_url}/{endpoint}"
        params = {**self._base_params(), **extra_params}
        resp = requests.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return self._safe_json(resp)

    # ---------- 엔드포인트 ----------
    def resolve_area_code(self, region_name: str) -> tuple[Optional[str], Optional[str]]:
        """areaCode2로 지역명을 지역코드로 해석한다(간단 부분일치).

        반환: (area_code, sigungu_code). sigungu는 현재 미사용으로 항상 None.
        """
        try:
            payload = self._get(
                "areaCode2",
                {"numOfRows": Config.AREA_CODE_NUM_ROWS, "pageNo": 1},
            )
            items = self._extract_items(payload)
            name = region_name or ""
            for suffix in REGION_NAME_SUFFIXES:
                name = name.replace(suffix, "")
            name = name.strip()
            candidates = [it for it in items if name and name in (it.get("name") or "")]
            if not candidates and items:
                candidates = items
            code = candidates[0].get("code") if candidates else None
            return (str(code) if code else None), None
        except Exception:
            return None, None

    def fetch_area_based_list(
        self,
        num_rows: int,
        area_code: Optional[str] = None,
        sigungu_code: Optional[str] = None,
        cat1: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """areaBasedList2로 지역 기반 관광지 목록을 조회한다(대표이미지 보장 정렬)."""
        extra: dict[str, Any] = {
            "numOfRows": num_rows,
            "pageNo": 1,
            "arrange": Config.LIST_ARRANGE,
        }
        if area_code:
            extra["areaCode"] = area_code
        if sigungu_code:
            extra["sigunguCode"] = sigungu_code
        if cat1:
            extra["cat1"] = cat1
        try:
            payload = self._get("areaBasedList2", extra)
            return self._extract_items(payload)
        except Exception as exc:
            print("[TourAPI] areaBasedList2 호출 오류:", exc)
            return []

    def fetch_detail_common(self, content_id: str) -> tuple[str, str]:
        """detailCommon2로 overview/homepage를 확보한다. 반환: (overview, homepage)."""
        if not content_id:
            return "", ""
        try:
            payload = self._get(
                "detailCommon2",
                {"numOfRows": Config.DETAIL_NUM_ROWS, "pageNo": 1, "contentId": content_id},
            )
            items = self._extract_items(payload)
            item = items[0] if items else {}
            overview = (item.get("overview") or "").strip()
            homepage = normalize_homepage(item.get("homepage") or "")
            return overview, homepage
        except Exception:
            return "", ""

    def fetch_detail_image(self, content_id: str) -> str:
        """detailImage2에서 검증을 통과하는 보조 이미지 1장을 확보한다."""
        if not content_id:
            return ""
        try:
            payload = self._get(
                "detailImage2",
                {"numOfRows": Config.DETAIL_NUM_ROWS, "pageNo": 1, "contentId": content_id},
            )
            for item in self._extract_items(payload):
                for field in ("originimgurl", "smallimageurl"):
                    valid = validate_image_url(item.get(field) or "")
                    if valid:
                        return valid
        except Exception:
            pass
        return ""
