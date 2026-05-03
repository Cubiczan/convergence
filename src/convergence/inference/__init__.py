"""DO Inference client — OpenAI-compatible API for DigitalOcean GenAI."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

# Lazy import to avoid requiring httpx in all environments
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

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
        """Send a chat completion request and return the assistant's text response."""
        use_model = DO_MODELS.get(model, model) if model else self.model
        payload = {
            "model": use_model,
            "messages": messages,
            "max_completion_tokens": max_tokens,
            "temperature": temperature,
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

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
