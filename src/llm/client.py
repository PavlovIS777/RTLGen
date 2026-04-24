from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(slots=True)
class LLMSettings:
    base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:8080")
    model_alias: str = os.getenv("LLM_MODEL_ALIAS", "local")
    system_prompt: str = os.getenv(
        "LLM_SYSTEM_PROMPT",
        "You are a careful coding assistant for Python, Verilog and SystemVerilog.",
    )
    timeout_sec: int = int(os.getenv("LLM_TIMEOUT_SEC", "600"))


class LlamaCppClient:
    def __init__(self, settings: LLMSettings | None = None):
        self.settings = settings or LLMSettings()

    def chat(
        self,
        user_prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        messages = []

        final_system = system_prompt if system_prompt is not None else self.settings.system_prompt
        if final_system:
            messages.append({"role": "system", "content": final_system})

        messages.append({"role": "user", "content": user_prompt})

        payload: dict[str, Any] = {
            "model": self.settings.model_alias,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = requests.post(
            f"{self.settings.base_url}/v1/chat/completions",
            json=payload,
            timeout=self.settings.timeout_sec,
        )
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    def wait_until_ready(self, attempts: int = 60, sleep_sec: float = 2.0) -> None:
        last_error: Exception | None = None

        for _ in range(attempts):
            try:
                _ = self.chat("Reply with exactly: OK", temperature=0.0, max_tokens=8)
                return
            except Exception as exc:
                last_error = exc
                time.sleep(sleep_sec)

        raise RuntimeError(f"LLM server did not become ready in time. Last error: {last_error}")
