# llm_client.py — OpenAI 클라이언트 래퍼(채팅 + 임베딩)
#
# 모든 OpenAI 접근을 이 한 클래스로 통일한다(클라이언트 인스턴스 중복 생성 제거).
# 도메인 프롬프트는 여기 두지 않고, 호출부(recommender/search_service)가 조립한다.
from __future__ import annotations

from typing import Any, Optional

from openai import OpenAI

from config import Config

# 채팅 메시지 타입 별칭
ChatMessage = dict[str, str]


class LLMClient:
    """OpenAI Chat Completions / Embeddings에 대한 얇은 래퍼.

    OpenAI Python SDK v1+ 인터페이스(``OpenAI`` 클라이언트)를 사용한다.
    클라이언트는 인스턴스 생성 시점에 만들어지므로(모듈 임포트 시점 아님)
    API 키 없이도 모듈 임포트는 안전하다.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        chat_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ) -> None:
        self._client = OpenAI(api_key=api_key or Config.OPENAI_API_KEY)
        self.chat_model = chat_model or Config.OPENAI_MODEL
        self.embedding_model = embedding_model or Config.OPENAI_EMBEDDING_MODEL

    def complete_chat(
        self,
        messages: list[ChatMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict[str, Any]] = None,
    ) -> str:
        """Chat Completion을 호출하고 첫 번째 응답 메시지 내용을 문자열로 반환한다."""
        kwargs: dict[str, Any] = {
            "model": model or self.chat_model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if response_format is not None:
            kwargs["response_format"] = response_format
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """문장 리스트를 임베딩 벡터 리스트로 변환한다."""
        resp = self._client.embeddings.create(model=self.embedding_model, input=texts)
        return [item.embedding for item in resp.data]
