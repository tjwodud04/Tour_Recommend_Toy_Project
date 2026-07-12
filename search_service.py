# search_service.py — 임베딩 시맨틱 캐시 + 추천 오케스트레이션
#
# 질의 임베딩을 JSONL 캐시에서 유사도 검색하여 재사용하고,
# 미스면 RecommendationService로 조회한 뒤 결과를 캐시에 적재한다.
from __future__ import annotations

import json
import math
import os
from typing import Any, Optional

from config import Config
from llm_client import LLMClient
from recommender import RecommendationService

Card = dict[str, Any]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """두 벡터의 코사인 유사도를 계산한다."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1e-9
    norm_b = math.sqrt(sum(y * y for y in b)) or 1e-9
    return dot / (norm_a * norm_b)


class VectorCache:
    """JSONL 파일 기반의 간단한 임베딩 캐시(검색/추가)."""

    def __init__(self, path: str, max_items: int) -> None:
        self.path = path                     # 캐시 파일 경로
        self.max = max_items                 # 최대 라인 수
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8"):
                pass  # 빈 파일 생성

    def _iter_records(self):
        """파일을 라인 단위 JSON 레코드로 순회한다."""
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue

    def search(self, query_vec: list[float], top_k: int = 1) -> list[dict[str, Any]]:
        """query_vec에 가장 유사한 상위 top_k 레코드를 반환한다."""
        scored: list[tuple[float, dict[str, Any]]] = []
        for record in self._iter_records():
            vec = record.get("embedding")
            if not isinstance(vec, list):
                continue
            scored.append((cosine_similarity(query_vec, vec), record))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [record for _, record in scored[:top_k]]

    def add(self, query: str, embedding: list[float], cards: list[Card]) -> None:
        """(질의, 임베딩, 카드) 한 라인을 추가한다(용량 초과 시 앞부분 삭제)."""
        rows = list(self._iter_records())
        rows.append({"query": query, "embedding": embedding, "cards": cards})
        if len(rows) > self.max:
            rows = rows[-self.max:]
        with open(self.path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")


class SearchService:
    """임베딩 캐시에서 재사용하고, 미스면 RecommendationService로 조회한다."""

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        recommender: Optional[RecommendationService] = None,
    ) -> None:
        # LLMClient를 임베딩과 추천(LLM)에서 공유해 클라이언트 중복 생성을 피한다.
        self.llm = llm or LLMClient()
        self.recommender = recommender or RecommendationService(llm=self.llm)
        self.cache = VectorCache(Config.VECTOR_CACHE_PATH, Config.MAX_CACHE_ITEMS)

    def search(self, query: str, top_k: Optional[int] = None) -> list[Card]:
        """질의 → 캐시 탐색 → (미스) 추천 조회 → 저장 → 카드 반환."""
        want = top_k or Config.NUM_RECOMMEND

        # 1) 질의 임베딩 생성
        query_vec = self.llm.embed([query])[0]

        # 2) 캐시 조회(유사도 임계 적용)
        hits = self.cache.search(query_vec, top_k=1)
        if hits:
            similarity = cosine_similarity(query_vec, hits[0]["embedding"])
            if similarity >= Config.CACHE_SIM_THRESHOLD:
                cards = hits[0].get("cards") or []
                return cards[:want]

        # 3) 미스 → 추천 조회
        cards = self.recommender.recommend(query, want=want)

        # 4) 성공 시 캐시 적재
        if cards:
            self.cache.add(query, query_vec, cards)

        return cards
