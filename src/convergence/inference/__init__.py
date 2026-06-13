"""DO Inference client — OpenAI-compatible API for DigitalOcean GenAI."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from cubiczan_resilience import RetriesExhausted, resilient

# Lazy import to avoid requiring httpx in all environments
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


class InferenceError(RuntimeError):
    """Typed domain exception for failures talking to the inference backend.

    Raised after retries/timeouts are exhausted so callers (e.g. API routes)
    can map it to a stable HTTP response without leaking transport details.
    """

DO_INFERENCE_BASE = "https://inference.do-ai.run/v1"
DO_MODELS = {
    "gpt-oss-20b": "openai/gpt-oss-20b",
    "gpt-oss-120b": "openai/gpt-oss-120b",
    "llama3.3-70b": "meta/llama-3.3-70b-instruct",
    "deepseek-r1-70b": "deepseek-ai/deepseek-r1-distill-llama-70b",
}
DEFAULT_MODEL = "gpt-oss-20b"


class DOInferenceClient:
    """Client for DigitalOcean's OpenAI-compatible inference API."""

    def __init__(self, *, api_key: Optional[str] = None, model: str = DEFAULT_MODEL,
                 base_url: str = DO_INFERENCE_BASE, timeout: float = 60.0) -> None:
        if not HAS_HTTPX:
            raise ImportError("httpx is required for DO Inference. Install with: pip install convergence[inference]")
        self.api_key = api_key or os.environ.get("MODEL_ACCESS_KEY", "")
        self.model = DO_MODELS.get(model, model)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def chat(self, messages: List[Dict[str, Any]], *, max_tokens: int = 1500,
             temperature: float = 0.3, model: Optional[str] = None) -> str:
        """Send a chat completion request and return the assistant's text response.

        Transient transport failures (timeouts, connection errors) and transient
        5xx/429 responses are retried with exponential backoff. On exhaustion any
        underlying httpx error is normalised to :class:`InferenceError`.
        """
        use_model = DO_MODELS.get(model, model) if model else self.model
        payload = {
            "model": use_model,
            "messages": messages,
            "max_completion_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            return self._post_chat(payload)
        except RetriesExhausted as exc:
            raise InferenceError(
                f"inference request failed after retries: {exc.last_exc!r}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            # Non-retryable status (e.g. 4xx) or a 5xx on the final attempt.
            status = exc.response.status_code
            raise InferenceError(f"inference backend returned HTTP {status}") from exc
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as exc:
            raise InferenceError(f"inference backend unreachable: {exc!r}") from exc

    def _post_chat(self, payload: Dict[str, Any]) -> str:
        """Single chat-completion round-trip, guarded by retry/backoff/timeout."""

        @resilient(
            timeout=self.timeout,
            max_attempts=3,
            retryable_exceptions=(httpx.TimeoutException, httpx.ConnectError),
        )
        def _do_request() -> str:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]

        return _do_request()

    def chat_sync(self, prompt: str, *, system: str = "", max_tokens: int = 1500,
                  temperature: float = 0.3) -> str:
        """Simple single-turn chat with optional system prompt."""
        messages: List[Dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, max_tokens=max_tokens, temperature=temperature)

    def list_models(self) -> List[str]:
        """List available models."""
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            return [m["id"] for m in resp.json().get("data", [])]
