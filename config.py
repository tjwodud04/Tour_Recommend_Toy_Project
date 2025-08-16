# config.py
from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    # ----- OpenAI -----
    OPENAI_API_KEY         = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL           = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
    OPENAI_IMAGE_MODEL     = "gpt-4o-mini-search-preview"  # (미사용)

    # ----- Korea Tourism API -----
    KOREA_TOURISM_API_BASE = "http://apis.data.go.kr/B551011/KorService2"
    # NOTE: decoding key(=사람이 읽을 수 있는 원문 키)를 .env로 넣으세요. requests가 인코딩합니다.
    KOREA_TOURISM_API_KEY  = os.getenv("KOREA_TOURISM_API_KEY")
    TIMEOUT                = 10  # seconds

    # ----- Streamlit -----
    STREAMLIT_PAGE_TITLE   = "한국 관광지 추천 데모"
    STREAMLIT_PAGE_ICON    = "🗺️"
    STREAMLIT_LAYOUT       = "wide"

    # ----- 추천 로직 -----
    NUM_RECOMMEND          = 5
    API_FETCH_MULTIPLIER   = 6   # 후보 확대용

    # ----- LLM 생성 -----
    MAX_TOKENS             = 600
    TEMPERATURE            = 0.3

    # ----- 이미지 검증/캐시 -----
    IMAGE_CACHE_TTL_SEC    = 7 * 24 * 3600
    IMAGE_CACHE_MAX        = 1000
    IMAGE_MIN_BYTES        = 1024
    IMAGE_MAX_BYTES        = 15 * 1024 * 1024
    IMAGE_ALLOWED_EXTS     = {"jpg", "jpeg", "png", "webp"}
    IMAGE_DENY_DOMAINS     = {"example.com", "localhost", "127.0.0.1"}
    IMAGE_REQUIRE_HEAD_OK  = True
    IMAGE_HEAD_WHITELIST_NOHEAD = {"tong.visitkorea.or.kr"}  # HEAD 우회 화이트리스트

    # ----- 경량 임베딩 캐시(로컬 파일 JSONL) -----
    VECTOR_CACHE_PATH      = os.getenv("VECTOR_CACHE_PATH", "vector_cache.jsonl")
    CACHE_SIM_THRESHOLD    = 0.82   # 코사인 유사도 임계
    MAX_CACHE_ITEMS        = 500

    # ----- (구버전 캐시 관련) -----
    CACHE_VERSION          = 2
