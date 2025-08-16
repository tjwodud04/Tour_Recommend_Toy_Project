# embedding_service.py — OpenAI 임베딩 전용 래퍼
from openai import OpenAI    # OpenAI v1 클라이언트
from config import Config    # 설정 주입
from typing import List      # 타입 힌트

class EmbeddingService:
    """문장 리스트를 임베딩 벡터로 변환하는 서비스"""

    def __init__(self):
        # OpenAI 클라이언트 초기화
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        # 사용할 임베딩 모델명 저장
        self.model  = Config.OPENAI_EMBEDDING_MODEL

    def embed(self, texts: List[str]) -> List[List[float]]:
        """입력 문장 리스트 → 벡터 리스트로 반환."""
        # OpenAI 임베딩 API 호출
        r = self.client.embeddings.create(model=self.model, input=texts)
        # 각 항목의 .embedding만 모아 반환
        return [d.embedding for d in r.data]
