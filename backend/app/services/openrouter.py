"""OpenRouter chat-completions client with bounded retries and sanitized logs."""

import logging
import random
import re
import time
from uuid import UUID

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from app.config import settings

logger = logging.getLogger(__name__)
GENERATION_MAX_RETRIES = 2
GENERATION_BASE_BACKOFF_SECONDS = 0.75
GENERATION_MAX_BACKOFF_SECONDS = 6.0


class OpenRouterGenerationError(RuntimeError):
    """Safe, user-independent error raised when OpenRouter cannot answer."""

    def __init__(self, message: str, *, status_code: int | None = None, retry_after: int | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class OpenRouterAnswerGenerator:
    def __init__(self):
        if not settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured for answer generation.")
        # Disable SDK retries so this bounded policy and its logs are authoritative.
        self.client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            timeout=settings.openrouter_timeout_seconds,
            max_retries=0,
            default_headers={
                "HTTP-Referer": settings.frontend_origin,
                "X-Title": "Document Chatbot",
            },
        )

    def generate(self, messages: list[dict[str, str]], correlation_id: UUID | str) -> str:
        started = time.perf_counter()
        fallback_models = [
            model for model in settings.openrouter_fallback_models
            if model != settings.openrouter_model
        ]
        for attempt in range(GENERATION_MAX_RETRIES + 1):
            try:
                extra_body = {"reasoning": {"effort": "low"}}
                if fallback_models:
                    # OpenRouter can route around provider/model errors in the
                    # same request. The application also checks empty 200s below.
                    extra_body["models"] = fallback_models
                response = self.client.chat.completions.create(
                    model=settings.openrouter_model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=2048,
                    extra_body=extra_body,
                )
                content, diagnostics = self._extract_content(response)
                if content:
                    return self._log_success(response, content, correlation_id, started, attempt + 1)

                logger.warning(
                    "workspace_rag.openrouter_empty_completion correlation_id=%s requested_model=%s served_model=%s finish_reason=%s completion_tokens=%s has_reasoning=%s refusal=%s request_id=%s",
                    correlation_id,
                    settings.openrouter_model,
                    getattr(response, "model", None),
                    diagnostics["finish_reason"],
                    diagnostics["completion_tokens"],
                    diagnostics["has_reasoning"],
                    diagnostics["refusal"],
                    getattr(response, "_request_id", None),
                )
                # A content-filter refusal should not be worked around. Other
                # successful-but-empty responses are a provider/model failure;
                # try one alternate model directly before returning an error.
                if diagnostics["finish_reason"] != "content_filter" and not diagnostics["refusal"]:
                    for fallback_model in fallback_models:
                        fallback_response = self.client.chat.completions.create(
                            model=fallback_model,
                            messages=messages,
                            temperature=0.2,
                            max_tokens=2048,
                            extra_body={"reasoning": {"effort": "low"}},
                        )
                        fallback_content, fallback_diagnostics = self._extract_content(fallback_response)
                        if fallback_content:
                            logger.warning(
                                "workspace_rag.openrouter_empty_response_fallback_succeeded correlation_id=%s requested_model=%s served_model=%s finish_reason=%s request_id=%s",
                                correlation_id,
                                settings.openrouter_model,
                                getattr(fallback_response, "model", fallback_model),
                                fallback_diagnostics["finish_reason"],
                                getattr(fallback_response, "_request_id", None),
                            )
                            return self._log_success(
                                fallback_response,
                                fallback_content,
                                correlation_id,
                                started,
                                attempt + 1,
                            )
                        logger.warning(
                            "workspace_rag.openrouter_fallback_empty_completion correlation_id=%s model=%s finish_reason=%s completion_tokens=%s has_reasoning=%s refusal=%s request_id=%s",
                            correlation_id,
                            fallback_model,
                            fallback_diagnostics["finish_reason"],
                            fallback_diagnostics["completion_tokens"],
                            fallback_diagnostics["has_reasoning"],
                            fallback_diagnostics["refusal"],
                            getattr(fallback_response, "_request_id", None),
                        )
                if diagnostics["refusal"]:
                    detail = "The answer provider declined this request. Rephrase the question and try again."
                elif diagnostics["finish_reason"] == "content_filter":
                    detail = "The answer provider could not return a response for this request. Rephrase it and try again."
                else:
                    detail = "OpenRouter returned an empty answer from the selected and fallback models. Please retry shortly."
                raise OpenRouterGenerationError(detail, status_code=502) from None
            except OpenRouterGenerationError:
                logger.error(
                    "workspace_rag.openrouter_malformed_response correlation_id=%s model=%s attempt=%d",
                    correlation_id,
                    settings.openrouter_model,
                    attempt + 1,
                )
                raise
            except (APITimeoutError, APIConnectionError) as error:
                if attempt >= GENERATION_MAX_RETRIES:
                    logger.error(
                        "workspace_rag.openrouter_transport_exhausted correlation_id=%s model=%s attempts=%d error_type=%s",
                        correlation_id,
                        settings.openrouter_model,
                        attempt + 1,
                        type(error).__name__,
                    )
                    raise OpenRouterGenerationError("OpenRouter request timed out or could not connect.") from None
                self._backoff(attempt, correlation_id, "transport")
            except APIStatusError as error:
                status = error.status_code
                # OpenRouter already attempts the configured alternate models
                # in this request. Repeating a 429 immediately burns more of
                # the account's limited free request allowance, so fail fast.
                if status == 429:
                    provider_code, provider_message = self._provider_error_details(error)
                    retry_after = self._retry_after(error)
                    logger.error(
                        "workspace_rag.openrouter_request_rate_limited correlation_id=%s model=%s status=429 provider_code=%s provider_message=%s retry_after_seconds=%s request_id=%s",
                        correlation_id,
                        settings.openrouter_model,
                        provider_code,
                        provider_message,
                        retry_after,
                        getattr(error, "request_id", None),
                    )
                    detail = (
                        "OpenRouter is rate-limiting free-model requests. Its free tier allows up to 20 requests per minute "
                        "and 50 per day for accounts without purchased credits. Please wait for the limit to reset and retry."
                    )
                    raise OpenRouterGenerationError(
                        detail,
                        status_code=429,
                        retry_after=retry_after,
                    ) from None

                retryable = status in (408, 409) or status >= 500
                if not retryable or attempt >= GENERATION_MAX_RETRIES:
                    category = "quota_or_credits" if status in (402, 403) else "provider_failure"
                    logger.error(
                        "workspace_rag.openrouter_request_failed correlation_id=%s model=%s status=%d category=%s attempts=%d request_id=%s",
                        correlation_id,
                        settings.openrouter_model,
                        status,
                        category,
                        attempt + 1,
                        getattr(error, "request_id", None),
                    )
                    if status == 401:
                        detail = "OpenRouter rejected the API key (HTTP 401). Check OPENROUTER_API_KEY."
                    elif status == 402:
                        detail = "OpenRouter has no available credits or free-tier quota (HTTP 402)."
                    elif status == 403:
                        detail = "OpenRouter denied this request (HTTP 403). Check account or model access."
                    elif status == 404:
                        detail = "OpenRouter model was not found (HTTP 404). Check OPENROUTER_MODEL."
                    else:
                        detail = f"OpenRouter request failed with HTTP {status}."
                    raise OpenRouterGenerationError(detail) from None
                self._backoff(attempt, correlation_id, f"http_{status}")
            except Exception as error:
                logger.error(
                    "workspace_rag.openrouter_unexpected_failure correlation_id=%s model=%s error_type=%s",
                    correlation_id,
                    settings.openrouter_model,
                    type(error).__name__,
                )
                raise OpenRouterGenerationError("OpenRouter answer generation failed unexpectedly.") from None
        raise OpenRouterGenerationError("OpenRouter answer generation failed after retries.")

    @staticmethod
    def _extract_content(response) -> tuple[str | None, dict[str, object]]:
        choices = getattr(response, "choices", None) or []
        choice = choices[0] if choices else None
        message = getattr(choice, "message", None)
        raw_content = getattr(message, "content", None)
        if isinstance(raw_content, str):
            content = raw_content.strip()
        elif isinstance(raw_content, list):
            text_parts = [
                getattr(part, "text", "")
                for part in raw_content
                if getattr(part, "type", None) == "text" and getattr(part, "text", None)
            ]
            content = "\n".join(text_parts).strip()
        else:
            content = ""
        usage = getattr(response, "usage", None)
        return content or None, {
            "finish_reason": getattr(choice, "finish_reason", None) or "unknown",
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "has_reasoning": bool(getattr(message, "reasoning", None)),
            "refusal": bool(getattr(message, "refusal", None)),
        }

    @staticmethod
    def _log_success(response, content: str, correlation_id: UUID | str, started: float, attempt: int) -> str:
        logger.info(
            "workspace_rag.openrouter_generation_completed correlation_id=%s model=%s attempt=%d duration_ms=%d output_chars=%d request_id=%s",
            correlation_id,
            getattr(response, "model", None) or settings.openrouter_model,
            attempt,
            round((time.perf_counter() - started) * 1000),
            len(content),
            getattr(response, "_request_id", None),
        )
        return content

    @staticmethod
    def _backoff(attempt: int, correlation_id: UUID | str, reason: str) -> None:
        delay = min(GENERATION_BASE_BACKOFF_SECONDS * (2**attempt), GENERATION_MAX_BACKOFF_SECONDS)
        delay = min(delay * random.uniform(0.8, 1.2), GENERATION_MAX_BACKOFF_SECONDS)
        logger.warning(
            "workspace_rag.openrouter_retry correlation_id=%s model=%s attempt=%d reason=%s delay_seconds=%.2f",
            correlation_id,
            settings.openrouter_model,
            attempt + 1,
            reason,
            delay,
        )
        time.sleep(delay)

    @staticmethod
    def _retry_after(error: APIStatusError) -> int | None:
        raw_value = error.response.headers.get("retry-after")
        if not raw_value:
            return None
        try:
            seconds = int(float(raw_value))
        except (TypeError, ValueError):
            return None
        return seconds if seconds > 0 else None

    @staticmethod
    def _provider_error_details(error: APIStatusError) -> tuple[str, str]:
        body = error.body if isinstance(error.body, dict) else {}
        payload = body.get("error", body)
        if not isinstance(payload, dict):
            return "unknown", "unspecified provider rate limit"
        code = str(payload.get("code") or "unknown")[:80]
        message = str(payload.get("message") or "unspecified provider rate limit")
        # Provider messages help distinguish minute and daily limits, but never
        # allow credentials or unbounded response text into application logs.
        api_key = settings.openrouter_api_key or ""
        if api_key:
            message = message.replace(api_key, "[redacted]")
        message = re.sub(r"sk-or-v1-[A-Za-z0-9_-]+", "[redacted]", message)
        message = re.sub(r"\s+", " ", message).strip()[:240]
        return code, message
