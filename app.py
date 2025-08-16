# app.py — Streamlit UI: 입력/실행/결과 카드 렌더링
import time, requests, streamlit as st           # 시간/HTTP/UI
from urllib.parse import urlparse                # URL 파싱
from config import Config                        # 설정 주입
from search_service import SearchService         # 검색 서비스

# ----- 페이지 기본 설정 -----
st.set_page_config(
    page_title=Config.STREAMLIT_PAGE_TITLE,      # 탭 타이틀
    page_icon=Config.STREAMLIT_PAGE_ICON,        # 아이콘
    layout=Config.STREAMLIT_LAYOUT               # 레이아웃
)

# ----- 세션 상태 초기화 -----
if "page" not in st.session_state: st.session_state.page = "홈"       # 현재 페이지
if "query" not in st.session_state: st.session_state.query = ""       # 입력 질의
if "results" not in st.session_state: st.session_state.results = None # 결과 캐시
if "last_elapsed" not in st.session_state: st.session_state.last_elapsed = None  # 소요시간

# ----- 서비스 인스턴스 -----
search_svc = SearchService()                     # 검색/추천 오케스트레이터

# ----- 이미지 검증 파라미터 -----
DENY_DOMAINS = set(getattr(Config, "IMAGE_DENY_DOMAINS", {"example.com", "localhost", "127.0.0.1"}))
ALLOWED_EXTS = set(getattr(Config, "IMAGE_ALLOWED_EXTS", {"jpg", "jpeg", "png", "webp"}))
HEAD_CHECK    = bool(getattr(Config, "IMAGE_REQUIRE_HEAD_OK", True))
MIN_BYTES     = int(getattr(Config, "IMAGE_MIN_BYTES", 1024))
MAX_BYTES     = int(getattr(Config, "IMAGE_MAX_BYTES", 15 * 1024 * 1024))
NOHEAD_WHITELIST = set(getattr(Config, "IMAGE_HEAD_WHITELIST_NOHEAD", set()))

def _domain_blocked(url: str) -> bool:
    """차단 도메인 검사."""
    try:
        host = urlparse(url).netloc.lower().split(":")[0]
    except Exception:
        return True
    return any(host == d or host.endswith("." + d) for d in DENY_DOMAINS)

def _ext_ok(url: str) -> bool:
    """확장자 검사."""
    path = urlparse(url).path.lower()
    return "." in path and path.rsplit(".", 1)[-1] in ALLOWED_EXTS

@st.cache_data(show_spinner=False, ttl=60 * 60)
def _fetch_image_bytes(url: str) -> bytes | None:
    """이미지 URL → 바이너리(HEAD 검증 포함)."""
    if not url or _domain_blocked(url) or not _ext_ok(url):
        return None
    host = urlparse(url).netloc.lower().split(":")[0]
    if HEAD_CHECK and host not in NOHEAD_WHITELIST:
        try:
            hr = requests.head(url, allow_redirects=True, timeout=5)
            if hr.status_code >= 400: return None
            ctype = (hr.headers.get("Content-Type") or "").lower()
            if not ctype.startswith("image/"): return None
            clen = hr.headers.get("Content-Length")
            if clen and clen.isdigit():
                n = int(clen)
                if n < MIN_BYTES or n > MAX_BYTES: return None
        except Exception:
            return None
    try:
        r = requests.get(url, stream=True, timeout=8)
        r.raise_for_status()
        total, chunks = 0, []
        for chunk in r.iter_content(chunk_size=8192):
            if not chunk: break
            total += len(chunk)
            if total > MAX_BYTES: return None
            chunks.append(chunk)
        data = b"".join(chunks)
        if len(data) < MIN_BYTES: return None
        return data
    except Exception:
        return None

def render_thumbnail(url: str):
    """카드 좌측 썸네일 렌더(실패 시 플레이스홀더)."""
    data = _fetch_image_bytes((url or "").strip())
    if data:
        st.image(data, use_container_width=True)
    else:
        st.markdown(
            """
            <div style="
                width:100%;
                aspect-ratio: 4 / 3;
                border-radius: 8px;
                overflow: hidden;
                background:#f2f2f2;
                color:#888;
                display:flex;
                align-items:center;
                justify-content:center;
            ">이미지 없음</div>
            """,
            unsafe_allow_html=True,
        )

def render_card(item: dict):
    """단일 추천 카드 렌더: 이미지/제목/요약/주소/홈페이지."""
    name = (item.get("name") or "").strip()           # 이름
    reason = (item.get("reason") or "").strip()       # 한 줄 요약
    address = (item.get("address") or "").strip() or "주소 정보 없음"
    image_url = (item.get("image_url") or "").strip()
    homepage = (item.get("homepage") or "").strip()   # 절대 URL

    with st.container(border=True):                   # 카드 컨테이너
        left, right = st.columns([1, 3])              # 좌우 분할
        with left:
            render_thumbnail(image_url)               # 썸네일
        with right:
            st.markdown(f"**{name or '이름 정보 없음'}**")  # 제목
            st.write(reason or "한 줄 설명 없음")          # 요약
            st.caption(f"📍 {address}")                # 주소
            if homepage:
                st.markdown(f"[🔗 홈페이지 바로가기]({homepage})")  # 링크

# ===== 사이드바 =====
with st.sidebar:
    st.header("📋 메뉴")                               # 메뉴 제목
    if st.button("🏠 홈", use_container_width=True):   # 홈 버튼
        st.session_state.page = "홈"
    if st.button("🔍 관광지 찾기", use_container_width=True):  # 검색 버튼
        st.session_state.page = "검색"
    st.markdown("---")                                 # 구분선

# ===== 본문 =====
st.title("한국 관광지 추천 데모")                      # 타이틀
st.markdown("---")                                     # 구분선

if st.session_state.page == "홈":
    # 홈 화면: 안내 문구
    st.header("🏠 환영합니다")
    st.markdown("좌측 **'관광지 찾기'** 메뉴에서 검색을 시작해 보세요.")

elif st.session_state.page == "검색":
    # 검색 화면: 입력/실행/리셋
    st.header("🔍 관광지 찾기")
    st.session_state.query = st.text_input(
        "찾고 싶은 관광지를 입력하세요:",
        value=st.session_state.query,
        placeholder="예: 제주 자연, 부산 박물관, 강릉 카페거리 등",
    )
    col_run, col_reset = st.columns([1, 1])
    with col_run:
        run_clicked = st.button("🔍 추천 받기", type="primary", use_container_width=True)
    with col_reset:
        reset_clicked = st.button("↺ 초기화", use_container_width=True)

    if reset_clicked:
        # 세션 초기화 후 리런
        st.session_state.query = ""
        st.session_state.results = None
        st.session_state.last_elapsed = None
        st.rerun()

    # 진행 상태 표시 홀더
    progress_ph = st.empty()
    status_ph   = st.empty()

    if run_clicked:
        if not st.session_state.query.strip():
            # 빈 입력 경고
            st.warning("검색어를 입력해 주세요.")
        else:
            start = time.time()                         # 시간 측정
            progress = progress_ph.progress(0, text="준비 중…")

            progress.progress(25, text="검색/분류 중…") # 1단계 진행
            with status_ph, st.spinner("🔎 관련 데이터 수집 중…"):
                # 검색 서비스 호출(임베딩 캐시 → API)
                items = search_svc.search(st.session_state.query, top_k=Config.NUM_RECOMMEND)

            progress.progress(90, text="후처리 중…")    # 2단계 진행

            # 결과/시간 세션 저장
            st.session_state.results = {"items": items}
            st.session_state.last_elapsed = time.time() - start
            # 진행 UI 정리
            progress_ph.empty(); status_ph.empty()

    # 결과 렌더
    if st.session_state.results is not None:
        items = st.session_state.results.get("items", []) or []
        if not items:
            st.info("조건에 맞는 추천 결과를 찾지 못했습니다. 키워드를 조금 더 구체화해 보세요.")
        else:
            st.success(f"추천 완료! ({st.session_state.last_elapsed:.2f}초)")
            st.markdown("#### 추천 목록")
            for it in items:
                render_card(it)
