# config.py — 전역 설정 로더
from dotenv import load_dotenv  # .env 읽기
import os                      # 환경변수 접근

load_dotenv()                  # .env 로드

class Config:
    # ----- OpenAI -----
    OPENAI_API_KEY         = os.getenv("OPENAI_API_KEY")          # OpenAI 키
    OPENAI_MODEL           = "gpt-4o-mini"                        # 텍스트 LLM
    OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"             # 임베딩 모델
    OPENAI_IMAGE_MODEL     = "gpt-4o-mini-search-preview"         # (미사용)

    # ----- Korea Tourism API -----
    KOREA_TOURISM_API_BASE = "http://apis.data.go.kr/B551011/KorService2"  # TourAPI 베이스
    KOREA_TOURISM_API_KEY  = os.getenv("KOREA_TOURISM_API_KEY")             # 디코딩 키 권장
    TIMEOUT                = 10                                             # HTTP 타임아웃

    # ----- Streamlit -----
    STREAMLIT_PAGE_TITLE   = "한국 관광지 추천 데모"   # 페이지 타이틀
    STREAMLIT_PAGE_ICON    = "🗺️"                      # 파비콘 이모지
    STREAMLIT_LAYOUT       = "wide"                    # 와이드 레이아웃

    # ----- 추천 로직 -----
    NUM_RECOMMEND          = 5     # 최종 카드 개수
    API_FETCH_MULTIPLIER   = 6     # 후보 확대용 배수

    # ----- LLM 생성 -----
    MAX_TOKENS             = 600   # 최대 토큰(여유분)
    TEMPERATURE            = 0.3   # 샘플링 온도

    # ----- 이미지 검증/캐시 -----
    IMAGE_CACHE_TTL_SEC    = 7 * 24 * 3600                    # 캐시 TTL
    IMAGE_CACHE_MAX        = 1000                             # 캐시 최대 엔트리
    IMAGE_MIN_BYTES        = 1024                             # 최소 바이트
    IMAGE_MAX_BYTES        = 15 * 1024 * 1024                 # 최대 바이트
    IMAGE_ALLOWED_EXTS     = {"jpg", "jpeg", "png", "webp"}   # 허용 확장자
    IMAGE_DENY_DOMAINS     = {"example.com", "localhost", "127.0.0.1"}  # 차단 도메인
    IMAGE_REQUIRE_HEAD_OK  = True                             # HEAD 검증 사용
    IMAGE_HEAD_WHITELIST_NOHEAD = {"tong.visitkorea.or.kr"}   # HEAD 우회 화이트리스트

    # ----- 경량 임베딩 캐시(JSONL) -----
    VECTOR_CACHE_PATH      = os.getenv("VECTOR_CACHE_PATH", "vector_cache.jsonl")  # 캐시 파일 경로
    CACHE_SIM_THRESHOLD    = 0.82   # 코사인 유사도 임계
    MAX_CACHE_ITEMS        = 500    # 캐시 최대 라인 수

    # ----- (구버전 캐시 버전 표식) -----
    CACHE_VERSION          = 2
