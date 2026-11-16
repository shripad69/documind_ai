"""OpenRouter chat-completions client with bounded candidate progression and sanitized logs."""

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

    def generate(
        self,
        messages: list[dict[str, str]],
        correlation_id: UUID | str,
        *,
        max_tokens: int = 4096,
        response_format: dict[str, str] | None = None,
        reasoning_effort: str = "none",
    ) -> str:
        started = time.perf_counter()

        # Build ordered deduplicated candidate models list: primary first, then fallbacks
        candidates: list[str] = []
        for model in [settings.openrouter_model, *settings.openrouter_fallback_models]:
            cleaned = model.strip() if isinstance(model, str) else ""
            if cleaned and cleaned not in candidates:
                candidates.append(cleaned)
        if not candidates:
            candidates = ["openrouter/free"]

        # When multiple candidates exist, iterate through each distinct candidate.
        # If only a single candidate is configured, retry that candidate up to GENERATION_MAX_RETRIES times.
        attempt_candidates = (
            candidates if len(candidates) > 1 else candidates * (GENERATION_MAX_RETRIES + 1)
        )

        attempt_index = 0
        transport_errors = 0
        empty_responses_count = 0
        had_rate_limit = False
        last_retry_after: int | None = None
        prev_candidate: str | None = None

        for candidate in attempt_candidates:
            attempt_index += 1

            # Back off only when retrying the exact same model candidate
            if prev_candidate is not None and candidate == prev_candidate:
                self._backoff(attempt_index - 1, correlation_id, f"retry_{candidate}")
            prev_candidate = candidate

            # OpenRouter native provider-level fallback array in extra_body (OpenRouter allows at most 3 items in 'models')
            other_models = [m for m in candidates if m != candidate]
            extra_body: dict[str, object] = {"reasoning": {"effort": reasoning_effort}}
            if other_models:
                extra_body["models"] = other_models[:3]

            create_kwargs = {
                "model": candidate,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": max_tokens,
                "extra_body": extra_body,
            }
            if response_format:
                create_kwargs["response_format"] = response_format

            try:
                response = self.client.chat.completions.create(**create_kwargs)
                content, diagnostics = self._extract_content(response)

                if content:
                    return self._log_success(
                        response,
                        content,
                        correlation_id,
                        started,
                        attempt=attempt_index,
                        requested_model=candidate,
                    )

                logger.warning(
                    "workspace_rag.openrouter_empty_completion correlation_id=%s requested_model=%s served_model=%s finish_reason=%s completion_tokens=%s has_reasoning=%s refusal=%s request_id=%s attempt=%d",
                    correlation_id,
                    candidate,
                    getattr(response, "model", None),
                    diagnostics["finish_reason"],
                    diagnostics["completion_tokens"],
                    diagnostics["has_reasoning"],
                    diagnostics["refusal"],
                    getattr(response, "_request_id", None),
                    attempt_index,
                )

                if diagnostics["refusal"]:
                    detail = "The answer provider declined this request. Rephrase the question and try again."
                    raise OpenRouterGenerationError(detail, status_code=502)
                if diagnostics["finish_reason"] == "content_filter":
                    detail = "The answer provider could not return a response for this request. Rephrase it and try again."
                    raise OpenRouterGenerationError(detail, status_code=502)

                # Do not retry this same candidate upon empty/reasoning-exhausted response; advance to next candidate
                empty_responses_count += 1
                continue

            except OpenRouterGenerationError:
                raise

            except (APITimeoutError, APIConnectionError) as error:
                transport_errors += 1
                logger.warning(
                    "workspace_rag.openrouter_transport_error correlation_id=%s requested_model=%s attempt=%d error_type=%s",
                    correlation_id,
                    candidate,
                    attempt_index,
                    type(error).__name__,
                )
                if transport_errors >= (GENERATION_MAX_RETRIES + 1):
                    logger.error(
                        "workspace_rag.openrouter_transport_exhausted correlation_id=%s requested_model=%s attempts=%d error_type=%s",
                        correlation_id,
                        candidate,
                        attempt_index,
                        type(error).__name__,
                    )
                    raise OpenRouterGenerationError("OpenRouter request timed out or could not connect.") from None
                continue

            except APIStatusError as error:
                status = error.status_code

                if status == 401:
                    detail = "OpenRouter rejected the API key (HTTP 401). Check OPENROUTER_API_KEY."
                    raise OpenRouterGenerationError(detail, status_code=401) from None

                if status == 402:
                    detail = "OpenRouter has no available credits or free-tier quota (HTTP 402)."
                    raise OpenRouterGenerationError(detail, status_code=402) from None

                if status == 429:
                    provider_code, provider_message = self._provider_error_details(error)
                    retry_after = self._retry_after(error)
                    last_retry_after = retry_after
                    had_rate_limit = True

                    # Distinguish account-level free quota exhaustion from upstream single-provider rate limits
                    is_account_limit = any(
                        phrase in provider_message.lower()
                        for phrase in (
                            "quota reached",
                            "free-models-per-day",
                            "free-models-per-minute",
                            "per-day quota",
                            "per-minute quota",
                            "rate limit reached",
                        )
                    )
                    if is_account_limit:
                        logger.error(
                            "workspace_rag.openrouter_request_rate_limited correlation_id=%s requested_model=%s status=429 provider_code=%s provider_message=%s retry_after_seconds=%s request_id=%s",
                            correlation_id,
                            candidate,
                            provider_code,
                            provider_message,
                            retry_after,
                            getattr(error, "request_id", None),
                        )
                        detail = (
                            "OpenRouter is rate-limiting free-model requests. Its free tier allows up to 20 requests per minute "
                            "and 50 per day for accounts without purchased credits. Please wait for the limit to reset and retry."
                        )
                        raise OpenRouterGenerationError(detail, status_code=429, retry_after=retry_after) from None

                    logger.warning(
                        "workspace_rag.openrouter_provider_rate_limited correlation_id=%s requested_model=%s status=429 provider_code=%s provider_message=%s retry_after_seconds=%s request_id=%s attempt=%d",
                        correlation_id,
                        candidate,
                        provider_code,
                        provider_message,
                        retry_after,
                        getattr(error, "request_id", None),
                        attempt_index,
                    )
                    continue

                if status == 404:
                    logger.warning(
                        "workspace_rag.openrouter_model_not_found correlation_id=%s requested_model=%s status=404 request_id=%s attempt=%d",
                        correlation_id,
                        candidate,
                        getattr(error, "request_id", None),
                        attempt_index,
                    )
                    continue

                logger.warning(
                    "workspace_rag.openrouter_provider_error correlation_id=%s requested_model=%s status=%d request_id=%s attempt=%d",
                    correlation_id,
                    candidate,
                    status,
                    getattr(error, "request_id", None),
                    attempt_index,
                )
                continue

            except Exception as error:
                logger.error(
                    "workspace_rag.openrouter_unexpected_failure correlation_id=%s requested_model=%s error_type=%s attempt=%d",
                    correlation_id,
                    candidate,
                    type(error).__name__,
                    attempt_index,
                )
                raise OpenRouterGenerationError("OpenRouter answer generation failed unexpectedly.") from None

        if transport_errors > 0 and transport_errors == len(attempt_candidates):
            raise OpenRouterGenerationError("OpenRouter request timed out or could not connect.")
        if empty_responses_count > 0 and empty_responses_count >= len(attempt_candidates):
            detail = "OpenRouter returned an empty answer from the selected and fallback models. Please retry shortly."
            raise OpenRouterGenerationError(detail, status_code=502)
        if had_rate_limit:
            detail = (
                "OpenRouter is rate-limiting free-model requests. Its free tier allows up to 20 requests per minute "
                "and 50 per day for accounts without purchased credits. Please wait for the limit to reset and retry."
            )
            raise OpenRouterGenerationError(detail, status_code=429, retry_after=last_retry_after)
        raise OpenRouterGenerationError(
            "OpenRouter was unable to generate an answer after trying all available models. Please retry shortly.",
            status_code=502,
        )

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
    def _log_success(
        response,
        content: str,
        correlation_id: UUID | str,
        started: float,
        attempt: int,
        requested_model: str,
    ) -> str:
        served_model = getattr(response, "model", None) or requested_model
        choices = getattr(response, "choices", None) or []
        choice = choices[0] if choices else None
        finish_reason = getattr(choice, "finish_reason", None) or "stop"
        logger.info(
            "workspace_rag.openrouter_generation_completed correlation_id=%s requested_model=%s served_model=%s finish_reason=%s attempt=%d duration_ms=%d output_chars=%d request_id=%s",
            correlation_id,
            requested_model,
            served_model,
            finish_reason,
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
            "workspace_rag.openrouter_retry correlation_id=%s attempt=%d reason=%s delay_seconds=%.2f",
            correlation_id,
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
        api_key = settings.openrouter_api_key or ""
        if api_key:
            message = message.replace(api_key, "[redacted]")
        message = re.sub(r"sk-or-v1-[A-Za-z0-9_-]+", "[redacted]", message)
        message = re.sub(r"\s+", " ", message).strip()[:240]
        return code, message
