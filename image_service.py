# image_service.py — 이미지 URL 검증/다운로드/캐시 (공용)
#
# UI(app.py)와 추천 로직(recommender.py)에서 공통으로 쓰던 이미지 검증 로직을
# 한곳으로 모아 중복을 제거한다.
from __future__ import annotations

import time
from typing import Optional
from urllib.parse import urlparse

import requests

from config import Config


def to_https(url: str) -> str:
    """``http://`` URL을 ``https://``로 승격한다(그 외는 그대로)."""
    url = (url or "").strip()
    if not url:
        return ""
    return "https://" + url[len("http://"):] if url.startswith("http://") else url


def _host_of(url: str) -> str:
    """URL에서 포트를 제외한 소문자 호스트를 추출한다."""
    return urlparse(url).netloc.lower().split(":")[0]


def is_domain_blocked(url: str) -> bool:
    """차단 도메인(또는 그 서브도메인)에 속하는지 검사한다."""
    try:
        host = _host_of(url)
    except Exception:
        return True
    return any(host == d or host.endswith("." + d) for d in Config.IMAGE_DENY_DOMAINS)


def has_allowed_extension(url: str) -> bool:
    """허용된 이미지 확장자를 가지는지 검사한다."""
    path = urlparse(url).path.lower()
    return "." in path and path.rsplit(".", 1)[-1] in Config.IMAGE_ALLOWED_EXTS


def head_ok(url: str) -> bool:
    """HEAD 요청으로 이미지 여부/크기를 검증한다.

    - ``IMAGE_REQUIRE_HEAD_OK``가 False면 검증을 생략(True).
    - 화이트리스트 호스트는 HEAD를 건너뛰고 통과(True).
    """
    if not Config.IMAGE_REQUIRE_HEAD_OK:
        return True
    host = _host_of(url)
    if host in Config.IMAGE_HEAD_WHITELIST_NOHEAD:
        return True
    try:
        resp = requests.head(url, allow_redirects=True, timeout=Config.IMAGE_HEAD_TIMEOUT)
        if resp.status_code >= 400:
            return False
        content_type = (resp.headers.get("Content-Type") or "").lower()
        if not content_type.startswith("image/"):
            return False
        content_length = resp.headers.get("Content-Length")
        if content_length and content_length.isdigit():
            size = int(content_length)
            if size < Config.IMAGE_MIN_BYTES or size > Config.IMAGE_MAX_BYTES:
                return False
        return True
    except Exception:
        return False


def validate_image_url(url: str) -> str:
    """https 승격 → 도메인/확장자/HEAD 검증을 모두 통과하면 URL을 반환(아니면 "")."""
    url = to_https(url)
    if not url or is_domain_blocked(url) or not has_allowed_extension(url) or not head_ok(url):
        return ""
    return url


def fetch_image_bytes(url: str) -> Optional[bytes]:
    """이미지 URL을 검증 후 바이너리로 내려받는다(실패 시 None).

    HEAD 검증(화이트리스트/설정에 따름) 후 스트리밍으로 다운로드하며,
    최소/최대 바이트 제한을 강제한다.
    """
    url = (url or "").strip()
    if not url or is_domain_blocked(url) or not has_allowed_extension(url):
        return None
    if not head_ok(url):
        return None
    try:
        resp = requests.get(url, stream=True, timeout=Config.IMAGE_GET_TIMEOUT)
        resp.raise_for_status()
        total, chunks = 0, []
        for chunk in resp.iter_content(chunk_size=Config.IMAGE_FETCH_CHUNK_SIZE):
            if not chunk:
                break
            total += len(chunk)
            if total > Config.IMAGE_MAX_BYTES:
                return None
            chunks.append(chunk)
        data = b"".join(chunks)
        if len(data) < Config.IMAGE_MIN_BYTES:
            return None
        return data
    except Exception:
        return None


class ImageUrlCache:
    """검증된 이미지 URL을 위한 간단한 TTL/용량 제한 캐시."""

    def __init__(self, ttl_sec: int, max_size: int) -> None:
        self.ttl = ttl_sec                                  # 만료 시간(초)
        self.max = max_size                                 # 최대 엔트리 수
        self.store: dict[str, tuple[str, float]] = {}       # {key: (url, saved_at)}

    def _expired(self, saved_at: float) -> bool:
        """TTL 기준 만료 여부."""
        return (time.time() - saved_at) > self.ttl if self.ttl > 0 else False

    def get(self, key: Optional[str]) -> str:
        """키로 URL을 조회한다(만료 시 제거 후 "")."""
        if not key:
            return ""
        entry = self.store.get(key)
        if not entry:
            return ""
        url, saved_at = entry
        if self._expired(saved_at):
            self.store.pop(key, None)
            return ""
        return url

    def set(self, key: Optional[str], url: str) -> None:
        """키에 URL을 저장한다(용량 초과 시 오래된 절반 제거)."""
        if not key or not url:
            return
        if self.max > 0 and len(self.store) >= self.max:
            oldest = sorted(self.store.items(), key=lambda kv: kv[1][1])[: max(1, self.max // 2)]
            for old_key, _ in oldest:
                self.store.pop(old_key, None)
        self.store[key] = (url, time.time())
