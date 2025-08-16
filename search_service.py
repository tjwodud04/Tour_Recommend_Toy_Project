# search_service.py — 임베딩 캐시 + DataService 호출 오케스트레이션
from typing import List, Dict                 # 타입 힌트
from config import Config                    # 설정
from data_service import DataService         # 데이터 서비스
from embedding_service import EmbeddingService  # 임베딩
import json, math, os                        # 파일/수학

def _cos_sim(a: list[float], b: list[float]) -> float:
    """두 벡터의 코사인 유사도 계산"""
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a)) or 1e-9
    nb = math.sqrt(sum(y*y for y in b)) or 1e-9
    return dot / (na * nb)

class _VecCache:
    """간단 JSONL 기반 임베딩 캐시(검색/추가)"""
    def __init__(self, path: str, max_items: int):
        self.path = path                                  # 파일 경로
        self.max  = max_items                             # 최대 라인
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f: pass  # 빈 파일 생성

    def _iter(self):
        """파일을 라인 단위 JSON으로 순회"""
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try: yield json.loads(line)
                except Exception: continue

    def search(self, qvec: list[float], top_k=1) -> list[dict]:
        """qvec에 가장 유사한 상위 top_k 레코드 반환"""
        scored = []
        for obj in self._iter():
            vec = obj.get("embedding")
            if not isinstance(vec, list): continue
            sim = _cos_sim(qvec, vec)
            scored.append((sim, obj))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [o for _, o in scored[:top_k]]

    def add(self, query: str, embedding: list[float], cards: list[dict]) -> None:
        """(질의, 임베딩, 카드) 한 라인 추가 — 용량 초과 시 앞부분 삭제"""
        rows = list(self._iter())
        rows.append({"query": query, "embedding": embedding, "cards": cards})
        if len(rows) > self.max:
            rows = rows[-self.max:]
        with open(self.path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

class SearchService:
    """임베딩 캐시에서 재사용하고, 미스면 DataService로 조회"""
    def __init__(self):
        self.data_svc = DataService()                           # 외부 데이터 I/O
        self.embedder = EmbeddingService()                      # 임베딩 생성기
        self.cache    = _VecCache(Config.VECTOR_CACHE_PATH,     # 로컬 캐시
                                  Config.MAX_CACHE_ITEMS)

    def search(self, query: str, top_k: int = None) -> List[Dict]:
        """질의 → 캐시 탐색 → (미스) API 조회 → 저장 → 카드 반환"""
        want = top_k or Config.NUM_RECOMMEND

        # 1) 임베딩 생성
        qv = self.embedder.embed([query])[0]

        # 2) 캐시 조회(유사도 임계 적용)
        hits = self.cache.search(qv, top_k=1)
        if hits:
            sim = _cos_sim(qv, hits[0]["embedding"])
            if sim >= Config.CACHE_SIM_THRESHOLD:
                cards = hits[0].get("cards") or []
                return cards[:want]

        # 3) 미스 → DataService 조회
        cards = self.data_svc.recommend_items(query, want=want)

        # 4) 성공 시 캐시 적재
        if cards:
            self.cache.add(query, qv, cards)

        # 5) 결과 반환
        return cards
