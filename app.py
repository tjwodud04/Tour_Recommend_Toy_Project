# app.py
import time, json, requests, streamlit as st
from urllib.parse import urlparse
from config import Config
from search_service import SearchService

st.set_page_config(
    page_title=Config.STREAMLIT_PAGE_TITLE,
    page_icon=Config.STREAMLIT_PAGE_ICON,
    layout=Config.STREAMLIT_LAYOUT
)

if "page" not in st.session_state: st.session_state.page = "홈"
if "query" not in st.session_state: st.session_state.query = ""
if "results" not in st.session_state: st.session_state.results = None
if "last_elapsed" not in st.session_state: st.session_state.last_elapsed = None

search_svc = SearchService()

DENY_DOMAINS = set(getattr(Config, "IMAGE_DENY_DOMAINS", {"example.com", "localhost", "127.0.0.1"}))
ALLOWED_EXTS = set(getattr(Config, "IMAGE_ALLOWED_EXTS", {"jpg", "jpeg", "png", "webp"}))
HEAD_CHECK    = bool(getattr(Config, "IMAGE_REQUIRE_HEAD_OK", True))
MIN_BYTES     = int(getattr(Config, "IMAGE_MIN_BYTES", 1024))
MAX_BYTES     = int(getattr(Config, "IMAGE_MAX_BYTES", 15 * 1024 * 1024))
NOHEAD_WHITELIST = set(getattr(Config, "IMAGE_HEAD_WHITELIST_NOHEAD", set()))

def _domain_blocked(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower().split(":")[0]
    except Exception:
        return True
    return any(host == d or host.endswith("." + d) for d in DENY_DOMAINS)

def _ext_ok(url: str) -> bool:
    path = urlparse(url).path.lower()
    return "." in path and path.rsplit(".", 1)[-1] in ALLOWED_EXTS

@st.cache_data(show_spinner=False, ttl=60 * 60)
def _fetch_image_bytes(url: str) -> bytes | None:
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
    name = (item.get("name") or "").strip()
    reason = (item.get("reason") or "").strip()
    address = (item.get("address") or "").strip() or "주소 정보 없음"
    image_url = (item.get("image_url") or "").strip()
    homepage = (item.get("homepage") or "").strip()  # data_service에서 절대URL로 정규화됨

    with st.container(border=True):
        left, right = st.columns([1, 3])
        with left:
            render_thumbnail(image_url)
        with right:
            st.markdown(f"**{name or '이름 정보 없음'}**")
            st.write(reason or "한 줄 설명 없음")
            st.caption(f"📍 {address}")
            if homepage:
                st.markdown(f"[🔗 홈페이지 바로가기]({homepage})")

# ===== sidebar =====
with st.sidebar:
    st.header("📋 메뉴")
    if st.button("🏠 홈", use_container_width=True): st.session_state.page = "홈"
    if st.button("🔍 관광지 찾기", use_container_width=True): st.session_state.page = "검색"
    st.markdown("---")

# ===== main =====
st.title("한국 관광지 추천 데모")
st.markdown("---")

if st.session_state.page == "홈":
    st.header("🏠 환영합니다")
    st.markdown("좌측 **'관광지 찾기'** 메뉴에서 검색을 시작해 보세요.")

elif st.session_state.page == "검색":
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
        st.session_state.query = ""
        st.session_state.results = None
        st.session_state.last_elapsed = None
        st.rerun()

    progress_ph = st.empty()
    status_ph = st.empty()

    if run_clicked:
        if not st.session_state.query.strip():
            st.warning("검색어를 입력해 주세요.")
        else:
            start = time.time()
            progress = progress_ph.progress(0, text="준비 중…")

            progress.progress(25, text="검색/분류 중…")
            with status_ph, st.spinner("🔎 관련 데이터 수집 중…"):
                items = search_svc.search(st.session_state.query, top_k=Config.NUM_RECOMMEND)

            progress.progress(90, text="후처리 중…")
            st.session_state.results = {"items": items}
            st.session_state.last_elapsed = time.time() - start
            progress_ph.empty(); status_ph.empty()

    if st.session_state.results is not None:
        items = st.session_state.results.get("items", []) or []
        if not items:
            st.info("조건에 맞는 추천 결과를 찾지 못했습니다. 키워드를 조금 더 구체화해 보세요.")
        else:
            st.success(f"추천 완료! ({st.session_state.last_elapsed:.2f}초)")
            st.markdown("#### 추천 목록")
            for it in items:
                render_card(it)
