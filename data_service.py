# data_service.py — TourAPI와 LLM을 묶어 최종 카드 목록 생성
import time, json, re, random, requests               # 표준/HTTP/랜덤
from typing import List, Dict, Tuple, Optional        # 타입 힌트
from urllib.parse import urlparse, unquote            # URL 파싱/디코드
from openai import OpenAI                             # OpenAI v1
from config import Config                             # 설정

# OpenAI 클라이언트(전역 1개) — 재사용
_client = OpenAI(api_key=Config.OPENAI_API_KEY)

# 대분류(cat1) 후보 — LLM이 이 중 하나만 선택하도록 안내
CAT1_CHOICES = [
    {"code": "A01", "name": "자연"},
    {"code": "A02", "name": "인문(문화/예술/역사)"},
    {"code": "A03", "name": "레포츠"},
    {"code": "A04", "name": "쇼핑"},
    {"code": "A05", "name": "음식"},
    {"code": "B02", "name": "숙박"},
    {"code": "C01", "name": "추천코스"},
]

# 지역 추정 폴백 단어들
_REGION_HINTS = [
    "서울","부산","대구","인천","광주","대전","울산","세종",
    "경기","강원","충북","충남","전북","전남","경북","경남",
    "제주","강원특별자치도","제주특별자치도"
]

# ----------------------------- 유틸 -----------------------------

def _compose_full_address(addr1: str, addr2: str) -> str:
    """addr1/addr2를 공백 결합."""
    a1, a2 = (addr1 or "").strip(), (addr2 or "").strip()
    return f"{a1} {a2}".strip() if a1 and a2 else (a1 or a2 or "")

def _to_https(url: str) -> str:
    """http → https 승격."""
    url = (url or "").strip()
    if not url: return ""
    return "https://" + url[len("http://"):] if url.startswith("http://") else url

def _ext_ok(url: str) -> bool:
    """허용 확장자 여부 확인."""
    p = urlparse(url).path.lower()
    return "." in p and p.rsplit(".", 1)[-1] in Config.IMAGE_ALLOWED_EXTS

def _domain_blocked(url: str) -> bool:
    """차단 도메인 매칭."""
    host = urlparse(url).netloc.lower().split(":")[0]
    return any(host == d or host.endswith("." + d) for d in Config.IMAGE_DENY_DOMAINS)

def _head_ok(url: str) -> bool:
    """이미지 HEAD 검증(화이트리스트면 스킵)."""
    if not Config.IMAGE_REQUIRE_HEAD_OK:
        return True
    host = urlparse(url).netloc.lower().split(":")[0]
    if host in Config.IMAGE_HEAD_WHITELIST_NOHEAD:
        return True
    try:
        r = requests.head(url, allow_redirects=True, timeout=5)
        if r.status_code >= 400: return False
        ctype = (r.headers.get("Content-Type") or "").lower()
        if not ctype.startswith("image/"): return False
        clen = r.headers.get("Content-Length")
        if clen and clen.isdigit():
            n = int(clen)
            if n < Config.IMAGE_MIN_BYTES or n > Config.IMAGE_MAX_BYTES: return False
        return True
    except Exception:
        return False

def _validate_image_url(url: str) -> str:
    """https/확장자/도메인/HEAD 검증 통과 시 사용."""
    url = _to_https(url)
    if not url or _domain_blocked(url) or not _ext_ok(url) or not _head_ok(url):
        return ""
    return url

def _normalize_homepage(raw: str) -> str:
    """detailCommon2.homepage를 절대URL로 정규화."""
    t = (raw or "").strip()
    if not t: return ""
    m = re.search(r'href=["\']([^"\']+)["\']', t, re.I)  # a 태그 내부 링크 추출
    if m: t = m.group(1).strip()
    t = t.replace("&amp;", "&")                          # HTML 엔티티 정리
    if t.startswith("//"): t = "https:" + t              # 스킴 보정
    if not re.match(r'^https?://', t, re.I): t = "https://" + t
    return _to_https(t)

class _ImageCache:
    """간단 이미지 URL 캐시(TTL/Max)."""
    def __init__(self, ttl_sec: int, max_size: int):
        self.ttl  = ttl_sec                   # 만료 시간
        self.max  = max_size                  # 최대 엔트리
        self.store: Dict[str, Tuple[str, float]] = {}  # {key: (url, saved_at)}

    def _expired(self, ts: float) -> bool:
        """만료 여부."""
        return (time.time() - ts) > self.ttl if self.ttl > 0 else False

    def get(self, key: Optional[str]) -> str:
        """키 조회(만료 시 제거)."""
        if not key: return ""
        v = self.store.get(key)
        if not v: return ""
        url, ts = v
        if self._expired(ts):
            self.store.pop(key, None); return ""
        return url

    def set(self, key: Optional[str], url: str) -> None:
        """키 저장(용량 초과 시 오래된 절반 제거)."""
        if not key or not url: return
        if self.max > 0 and len(self.store) >= self.max:
            old = sorted(self.store.items(), key=lambda kv: kv[1][1])[: max(1, self.max // 2)]
            for k, _ in old: self.store.pop(k, None)
        self.store[key] = (url, time.time())

# ----------------------------- 서비스 -----------------------------

class DataService:
    """(region, cat1) 추출 → 지역코드 → TourAPI 목록/상세 → 요약/이미지 → 카드 생성."""

    def __init__(self):
        # 베이스 URL/키/타임아웃 설정
        self.base_url = Config.KOREA_TOURISM_API_BASE
        self.api_key  = Config.KOREA_TOURISM_API_KEY
        self.timeout  = Config.TIMEOUT
        # 이미지 캐시 인스턴스
        self._img_cache = _ImageCache(Config.IMAGE_CACHE_TTL_SEC, Config.IMAGE_CACHE_MAX)

    # ---------- 공용: API 키/JSON ----------
    def _api_key(self) -> str:
        """인코딩 키가 와도 안전 사용(디코드/공백제거)."""
        k = (self.api_key or "").strip()
        if "%" in k: k = unquote(k)
        return k.replace(" ", "")

    @staticmethod
    def _safe_json(resp: requests.Response) -> dict:
        """JSON 응답만 파싱(아닐 경우 본문 앞부분 포함 에러)."""
        ct = (resp.headers.get("Content-Type") or "").lower()
        text = (resp.text or "").strip()
        if "json" in ct or (text and (text.startswith("{") or text.startswith("["))):
            try: return resp.json()
            except Exception: pass
        head = text[:300].replace("\n"," ") if text else ""
        raise ValueError(f"Non-JSON response (status={resp.status_code}, ct='{ct}'). Body head: {head}")

    # ---------- 1) (region, cat1) ----------
    def _extract_region_and_cat1(self, user_query: str) -> Tuple[str, Optional[str]]:
        """LLM으로 지역 1개 + cat1 코드 1개 추출(실패 시 지역 폴백)."""
        try:
            cat_list = "\n".join([f"- {c['code']} : {c['name']}" for c in CAT1_CHOICES])
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
            # JSON 강제 출력
            resp = _client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=[
                    {"role":"system","content":"반드시 유효한 JSON만 출력하세요."},
                    {"role":"user","content": prompt},
                ],
                temperature=0.0, max_tokens=120,
                response_format={"type": "json_object"},
            )
            data   = json.loads(resp.choices[0].message.content or "{}")
            region = (data.get("region") or "").strip()
            cat1   = (data.get("cat1") or "").strip().upper()
            # cat1 검증
            if cat1 not in {c["code"] for c in CAT1_CHOICES}: cat1 = None
            # 지역 폴백
            if not region:
                t = (user_query or "").strip()
                region = next((w for w in _REGION_HINTS if w in t), t)
            return region, cat1
        except Exception:
            t = (user_query or "").strip()
            region = next((w for w in _REGION_HINTS if w in t), t)
            return region, None

    # ---------- 1-1) 지역명 → areaCode ----------
    def _resolve_area_code(self, region_name: str) -> Tuple[Optional[str], Optional[str]]:
        """areaCode2로 지역 코드 해석(간단 부분일치)."""
        url = f"{self.base_url}/areaCode2"
        p = {"serviceKey": self._api_key(), "numOfRows": 100, "pageNo": 1,
             "MobileOS": "ETC", "MobileApp": "TourAPI", "_type": "json"}
        try:
            r = requests.get(url, params=p, timeout=self.timeout); r.raise_for_status()
            items = self._safe_json(r).get("response",{}).get("body",{}).get("items",{}).get("item",[]) or []
            name = (region_name or "").replace("특별자치도","").replace("광역시","").replace("특별시","").strip()
            cand = [it for it in items if name and name in (it.get("name") or "")]
            if not cand and items: cand = items
            code = (cand[0].get("code") if cand else None)
            return (str(code) if code else None), None
        except Exception:
            return None, None

    # ---------- 2) 상세/요약/이미지 ----------
    def _fetch_detail_common(self, content_id: str) -> Tuple[str, str]:
        """detailCommon2로 overview/homepage 확보."""
        if not content_id: return "", ""
        url = f"{self.base_url}/detailCommon2"
        params = {"serviceKey": self._api_key(), "numOfRows": 1, "pageNo": 1,
                  "MobileOS": "ETC", "MobileApp": "TourAPI", "_type": "json",
                  "contentId": content_id}
        try:
            r = requests.get(url, params=params, timeout=self.timeout); r.raise_for_status()
            item = (self._safe_json(r).get("response",{}).get("body",{}).get("items",{}).get("item",[{}]))[0]
            overview = (item.get("overview") or "").strip()
            homepage = _normalize_homepage(item.get("homepage") or "")
            return overview, homepage
        except Exception:
            return "", ""

    def _fetch_detail_image(self, content_id: str) -> str:
        """detailImage2에서 보조 이미지 1장 확보."""
        url = f"{self.base_url}/detailImage2"
        p = {"serviceKey": self._api_key(), "numOfRows": 1, "pageNo": 1,
             "MobileOS": "ETC", "MobileApp": "TourAPI", "_type": "json",
             "contentId": content_id}
        try:
            r = requests.get(url, params=p, timeout=self.timeout); r.raise_for_status()
            items = self._safe_json(r).get("response",{}).get("body",{}).get("items",{}).get("item",[])
            if isinstance(items, dict): items=[items]
            for it in items or []:
                for k in ("originimgurl","smallimageurl"):
                    v = _validate_image_url(it.get(k) or "")
                    if v: return v
        except Exception:
            pass
        return ""

    def _summarize_one_line(self, text: str) -> str:
        """overview를 한국어 1문장(28~48자 내)으로 요약(금지어 회피, 폴백 포함)."""
        t = (text or "").strip()
        if not t: return ""
        try:
            resp = _client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=[
                    {"role":"system","content":"한국어 문장 하나로만 답해. 금지어: 요약,정리,한줄,한 문장. 28~48자."},
                    {"role":"user","content":
                     "예시입력: 천지연폭포는 계곡과 숲길이 아름답다.\n"
                     "예시출력: 숲길과 어우러진 천지연폭포의 경치를 즐길 수 있다.\n\n"
                     f"다음 글을 같은 형식으로 요약:\n{t}"}
                ],
                temperature=0.0, max_tokens=80
            )
            s = (resp.choices[0].message.content or "").strip()
            s = re.split(r"[.!?。]\s*", s)[0].strip()
            return (s + ".") if s else ""
        except Exception:
            s = re.split(r"[.!?。]\s*", t)[0].strip()
            return (s[:40] + ("..." if len(s) > 40 else ""))

    # ---------- 3) 목록 정리 ----------
    def _clean_items(self, items: List[Dict]) -> List[Dict]:
        """상업매장 등 비목적 항목 간단 필터."""
        ok = []
        for it in items:
            title = (it.get("title") or "").strip()
            if not title: continue
            if re.search(r"(대리점|지점|점$|마트|백화점|면세점|아울렛|할인점|스토어)", title):
                continue
            ok.append(it)
        return ok

    # ---------- 4) 이미지 선택 ----------
    def _pick_valid_image(self, cid_key: str, firstimage2: str, firstimage: str) -> str:
        """캐시 → firstimage2 → firstimage → detailImage2 순서."""
        cached = self._img_cache.get(cid_key)
        if cached: return cached
        for raw in (firstimage2, firstimage):
            valid = _validate_image_url(raw)
            if valid:
                self._img_cache.set(cid_key, valid)
                return valid
        img = self._fetch_detail_image(cid_key)
        if img: self._img_cache.set(cid_key, img)
        return img

    # ---------- 메인 ----------
    def recommend_items(self, user_query: str, want: int = None) -> List[Dict]:
        """사용자 질의 → (지역/분류) → 목록 → 상세/요약 → 카드 N개 생성."""
        want = want or Config.NUM_RECOMMEND

        # 1) 지역/대분류 추출
        region, cat1 = self._extract_region_and_cat1(user_query)
        area_code, sigungu_code = self._resolve_area_code(region)

        # 2) 지역 기반 목록(areaBasedList2) 조회 — 이미지 보장 정렬
        url = f"{self.base_url}/areaBasedList2"
        num_rows = max(80, want * Config.API_FETCH_MULTIPLIER)
        params = {
            "serviceKey": self._api_key(),
            "numOfRows": num_rows,
            "pageNo": 1,
            "arrange": "O",          # O/Q/R: 이미지 보장
            "MobileOS": "ETC",
            "MobileApp": "TourAPI",
            "_type": "json",
        }
        if area_code:   params["areaCode"]   = area_code
        if sigungu_code:params["sigunguCode"]= sigungu_code
        if cat1:        params["cat1"]       = cat1

        # 3) 호출/파싱
        try:
            r = requests.get(url, params=params, timeout=self.timeout)
            r.raise_for_status()
            payload = self._safe_json(r)
            items = (payload.get("response", {})
                            .get("body", {})
                            .get("items", {})
                            .get("item", [])) or []
            if not isinstance(items, list): items = [items]
        except Exception as e:
            print("[TourAPI] areaBasedList2 호출 오류:", e)
            items = []

        # 4) 휴리스틱 클린
        items = self._clean_items(items)
        if not items: return []

        # 5) 샘플링
        sample = random.sample(items, k=min(want, len(items)))

        # 6) 상세/요약/이미지 후 카드화
        out: List[Dict] = []
        for it in sample:
            cid   = (it.get("contentid") or "").strip()
            title = (it.get("title") or "").replace("<b>", "").replace("</b>", "").strip()
            addr  = _compose_full_address((it.get("addr1") or ""), (it.get("addr2") or ""))

            overview, homepage = self._fetch_detail_common(cid)
            reason = self._summarize_one_line(overview) or (overview[:120] + "..." if overview else "")

            img = self._pick_valid_image(
                cid,
                _to_https((it.get("firstimage2") or "")),
                _to_https((it.get("firstimage")  or "")),
            )

            out.append({
                "name": title or "이름 정보 없음",
                "reason": reason or "한 줄 설명 없음",
                "address": addr or "주소 정보 없음",
                "image_url": img,
                "homepage": homepage,
                "metadata": {
                    "contentid": cid,
                    "cat1": (it.get("cat1") or ""),
                    "addr1": (it.get("addr1") or ""),
                    "firstimage2": (it.get("firstimage2") or ""),
                    "title": title,
                    "region": region,
                }
            })

        # 7) 정확히 want개 반환(부족 시 있는 만큼)
        return out[:want]
