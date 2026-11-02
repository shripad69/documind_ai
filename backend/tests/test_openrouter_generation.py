from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from openai import APIStatusError, APITimeoutError

from app.services.openrouter import OpenRouterAnswerGenerator, OpenRouterGenerationError


def rag_with_responses(*responses):
    rag = OpenRouterAnswerGenerator.__new__(OpenRouterAnswerGenerator)
    calls = []

    class Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            response = responses[min(len(calls) - 1, len(responses) - 1)]
            if isinstance(response, Exception):
                raise response
            return response

    rag.client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    return rag, calls


def completion(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))], _request_id="test-request")


def empty_completion(*, finish_reason="stop", refusal=None, reasoning=None):
    message = SimpleNamespace(content=None, refusal=refusal, reasoning=reasoning)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], usage=SimpleNamespace(completion_tokens=12), _request_id="empty-request")


def api_status_error(status, *, headers=None, message="provider error"):
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx.Response(status, headers=headers or {}, request=request)
    return APIStatusError(message, response=response, body={"error": {"code": status, "message": message}})


def test_generation_sends_configured_chat_completion_and_returns_text(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "openrouter_model", "test/model:free")
    monkeypatch.setattr(settings, "openrouter_fallback_models", ("test/fallback:free",))
    rag, calls = rag_with_responses(completion(" Grounded answer [Source 1] "))
    messages = [{"role": "system", "content": "PDF context"}, {"role": "user", "content": "Question?"}]

    answer = rag.generate(messages, uuid4())

    assert answer == "Grounded answer [Source 1]"
    assert calls[0]["model"] == "test/model:free"
    assert calls[0]["messages"] == messages
    assert calls[0]["max_tokens"] == 2048
    assert calls[0]["extra_body"] == {
        "reasoning": {"effort": "low"},
        "models": ["test/fallback:free"],
    }


def test_rate_limit_fails_fast_after_provider_model_fallback_and_preserves_retry_after():
    rag, calls = rag_with_responses(
        api_status_error(429, headers={"Retry-After": "60"}, message="free-models-per-day quota reached")
    )

    with pytest.raises(OpenRouterGenerationError, match="20 requests per minute") as captured:
        rag.generate([], uuid4())
    assert captured.value.status_code == 429
    assert captured.value.retry_after == 60
    assert len(calls) == 1


def test_provider_server_error_retries_then_succeeds(monkeypatch):
    rag, calls = rag_with_responses(api_status_error(503), completion("Recovered"))
    monkeypatch.setattr("app.services.openrouter.time.sleep", lambda _: None)

    assert rag.generate([], uuid4()) == "Recovered"
    assert len(calls) == 2


def test_quota_or_credits_error_fails_without_retry(monkeypatch):
    rag, calls = rag_with_responses(api_status_error(402))

    with pytest.raises(OpenRouterGenerationError, match="credits or free-tier quota"):
        rag.generate([], uuid4())
    assert len(calls) == 1


def test_empty_success_response_uses_direct_fallback_model(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "openrouter_model", "test/model:free")
    monkeypatch.setattr(settings, "openrouter_fallback_models", ("test/fallback:free",))
    rag, calls = rag_with_responses(empty_completion(), completion("Fallback answer"))

    assert rag.generate([], uuid4()) == "Fallback answer"
    assert len(calls) == 2
    assert calls[0]["model"] == "test/model:free"
    assert calls[1]["model"] == "test/fallback:free"


def test_empty_success_from_all_models_returns_safe_provider_error(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "openrouter_model", "test/model:free")
    monkeypatch.setattr(settings, "openrouter_fallback_models", ("test/fallback:free",))
    rag, calls = rag_with_responses(empty_completion())

    with pytest.raises(OpenRouterGenerationError, match="empty answer") as captured:
        rag.generate([], uuid4())
    assert captured.value.status_code == 502
    assert len(calls) == 2


def test_provider_refusal_does_not_try_fallback(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "openrouter_model", "test/model:free")
    monkeypatch.setattr(settings, "openrouter_fallback_models", ("test/fallback:free",))
    rag, calls = rag_with_responses(empty_completion(refusal="request declined"))

    with pytest.raises(OpenRouterGenerationError, match="declined this request"):
        rag.generate([], uuid4())
    assert len(calls) == 1


def test_timeout_uses_bounded_retries_then_returns_safe_error(monkeypatch):
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    timeout = APITimeoutError(request=request)
    rag, calls = rag_with_responses(timeout)
    monkeypatch.setattr("app.services.openrouter.time.sleep", lambda _: None)

    with pytest.raises(OpenRouterGenerationError, match="timed out or could not connect"):
        rag.generate([], uuid4())
    assert len(calls) == 3
