# config.py — 전역 설정 로더
#
# 모든 튜닝 값/엔드포인트/모델명을 한곳에 모아둔 설정 클래스.
# 비밀 키는 절대 하드코딩하지 않고 환경변수(.env)에서만 읽는다.
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()  # 프로젝트 루트의 .env 로드


class Config:
    """애플리케이션 전역 설정.

    - 비밀 값(API 키)은 ``os.getenv``로만 주입한다(하드코딩 금지).
    - 그 외 엔드포인트/모델명/매직넘버는 의미 있는 상수로 정의한다.
    """

    # ----- OpenAI -----
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")   # OpenAI 키(비밀)
    OPENAI_MODEL: str = "gpt-4o-mini"                          # 텍스트 LLM
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"     # 임베딩 모델
    OPENAI_IMAGE_MODEL: str = "gpt-4o-mini-search-preview"     # (미사용, 참고용)

    # ----- Korea Tourism API(TourAPI) -----
    KOREA_TOURISM_API_BASE: str = "http://apis.data.go.kr/B551011/KorService2"  # 베이스 URL
    KOREA_TOURISM_API_KEY: str | None = os.getenv("KOREA_TOURISM_API_KEY")      # 디코딩 키 권장(비밀)
    TIMEOUT: int = 10                                                           # HTTP 타임아웃(초)

    # TourAPI 공통 요청 파라미터(모든 호출에서 동일하게 사용)
    TOURAPI_MOBILE_OS: str = "ETC"
    TOURAPI_MOBILE_APP: str = "TourAPI"
    TOURAPI_RESPONSE_TYPE: str = "json"
    # 목록/상세 조회 페이지 크기 및 정렬
    AREA_CODE_NUM_ROWS: int = 100    # areaCode2 조회 행 수
    DETAIL_NUM_ROWS: int = 1         # detailCommon2/detailImage2 행 수
    LIST_ARRANGE: str = "O"          # areaBasedList2 정렬(O/Q/R: 대표이미지 보장)
    MIN_LIST_ROWS: int = 80          # 후보 목록 최소 조회 행 수
    BODY_PREVIEW_LEN: int = 300      # 비정상(Non-JSON) 응답 본문 미리보기 길이

    # ----- Streamlit -----
    STREAMLIT_PAGE_TITLE: str = "한국 관광지 추천 데모"   # 페이지 타이틀
    STREAMLIT_PAGE_ICON: str = "🗺️"                      # 파비콘 이모지
    STREAMLIT_LAYOUT: str = "wide"                       # 와이드 레이아웃

    # ----- 추천 로직 -----
    NUM_RECOMMEND: int = 5           # 최종 카드 개수
    API_FETCH_MULTIPLIER: int = 6    # 후보 확대용 배수

    # ----- LLM 생성 파라미터 -----
    # 지역/대분류(cat1) 추출용
    EXTRACT_TEMPERATURE: float = 0.0
    EXTRACT_MAX_TOKENS: int = 120
    # 한 줄 요약용
    SUMMARY_TEMPERATURE: float = 0.0
    SUMMARY_MAX_TOKENS: int = 80
    SUMMARY_MIN_CHARS: int = 28       # 요약 목표 최소 글자 수(프롬프트 지시)
    SUMMARY_MAX_CHARS: int = 48       # 요약 목표 최대 글자 수(프롬프트 지시)
    SUMMARY_FALLBACK_LEN: int = 40    # LLM 실패 시 원문 절단 길이
    OVERVIEW_FALLBACK_LEN: int = 120  # 요약 실패 시 overview 절단 길이

    # ----- 이미지 검증/캐시 -----
    IMAGE_CACHE_TTL_SEC: int = 7 * 24 * 3600                  # 이미지 URL 캐시 TTL(초)
    IMAGE_CACHE_MAX: int = 1000                               # 이미지 URL 캐시 최대 엔트리
    IMAGE_MIN_BYTES: int = 1024                               # 최소 바이트
    IMAGE_MAX_BYTES: int = 15 * 1024 * 1024                   # 최대 바이트
    IMAGE_ALLOWED_EXTS: set[str] = {"jpg", "jpeg", "png", "webp"}   # 허용 확장자
    IMAGE_DENY_DOMAINS: set[str] = {"example.com", "localhost", "127.0.0.1"}  # 차단 도메인
    IMAGE_REQUIRE_HEAD_OK: bool = True                        # HEAD 검증 사용 여부
    IMAGE_HEAD_WHITELIST_NOHEAD: set[str] = {"tong.visitkorea.or.kr"}  # HEAD 우회 화이트리스트

    # 이미지 바이트 다운로드(썸네일용) 세부 파라미터
    IMAGE_HEAD_TIMEOUT: int = 5        # HEAD 요청 타임아웃(초)
    IMAGE_GET_TIMEOUT: int = 8         # GET(다운로드) 타임아웃(초)
    IMAGE_FETCH_CHUNK_SIZE: int = 8192  # 스트리밍 청크 크기(바이트)
    IMAGE_BYTES_CACHE_TTL_SEC: int = 60 * 60  # Streamlit 바이트 캐시 TTL(초)

    # ----- 경량 임베딩 캐시(JSONL) -----
    VECTOR_CACHE_PATH: str = os.getenv("VECTOR_CACHE_PATH", "vector_cache.jsonl")  # 캐시 파일 경로
    CACHE_SIM_THRESHOLD: float = 0.82   # 코사인 유사도 임계
    MAX_CACHE_ITEMS: int = 500          # 캐시 최대 라인 수

    # ----- (구버전 캐시 버전 표식) -----
    CACHE_VERSION: int = 2
