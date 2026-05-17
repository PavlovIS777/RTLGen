from __future__ import annotations

import os
import json
import time
from dataclasses import dataclass
from typing import Any

import requests


def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


def _env_raw(name: str, default: str) -> str:
    return os.getenv(name, default)


def json_dumps_compact(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


@dataclass(slots=True)
class ModelSettings:
    provider: str = _env("MODEL_PROVIDER", "openai_compatible")
    base_url: str = _env("MODEL_BASE_URL", os.getenv("LLM_BASE_URL", "http://localhost:8080"))
    api_key: str = _env("MODEL_API_KEY", "")
    model_name: str = _env("MODEL_NAME", os.getenv("LLM_MODEL_ALIAS", os.getenv("MODEL_ALIAS", "local")))
    system_prompt: str = _env(
        "MODEL_SYSTEM_PROMPT",
        os.getenv(
            "LLM_SYSTEM_PROMPT",
            "You are a careful coding assistant for Python, Verilog and SystemVerilog.",
        ),
    )
    timeout_sec: int = int(_env("MODEL_TIMEOUT_SEC", os.getenv("LLM_TIMEOUT_SEC", "600")))
    ready_timeout_sec: int = int(_env("MODEL_READY_TIMEOUT_SEC", os.getenv("LLM_READY_TIMEOUT_SEC", "120")))
    ready_poll_sec: float = float(_env("MODEL_READY_POLL_SEC", os.getenv("LLM_READY_POLL_SEC", "3")))
    max_retries: int = int(_env("MODEL_MAX_RETRIES", "3"))
    retry_backoff_sec: float = float(_env("MODEL_RETRY_BACKOFF_SEC", "2"))
    token_param: str = _env("MODEL_TOKEN_PARAM", "auto")
    user_suffix: str = _env_raw("MODEL_USER_SUFFIX", "")
    reasoning_content_mode: str = _env("MODEL_REASONING_CONTENT_MODE", "ignore")


class ModelClient:
    def __init__(self, settings: ModelSettings | None = None):
        self.settings = settings or ModelSettings()
        self._resolved_model_name: str | None = None

    @property
    def provider(self) -> str:
        return self.settings.provider or "openai_compatible"

    def _trim(self, text: str, max_len: int = 4000) -> str:
        text = (text or "").strip()
        if len(text) <= max_len:
            return text
        head = text[: max_len // 2]
        tail = text[-max_len // 2 :]
        return head + "\n...\n" + tail

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"
        return headers

    def _api_url(self, endpoint: str) -> str:
        base = self.settings.base_url.rstrip("/")
        endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        if base.endswith("/v1") or base.endswith("/v1beta/openai") or base.endswith("/compatible-mode/v1"):
            return f"{base}{endpoint}"
        return f"{base}/v1{endpoint}"

    def _is_retryable(self, status_code: int) -> bool:
        return status_code in {408, 409, 425, 429, 500, 502, 503, 504}

    def _user_prompt_with_suffix(self, user_prompt: str) -> str:
        suffix = self.settings.user_suffix
        if not suffix:
            return user_prompt
        if user_prompt.rstrip().endswith(suffix.strip()):
            return user_prompt
        return f"{user_prompt}{suffix}"

    def _token_param_name(self, model_name: str) -> str:
        configured = self.settings.token_param.strip()
        if configured and configured != "auto":
            return configured
        base = self.settings.base_url.lower()
        model = model_name.lower()
        if "api.openai.com" in base or model.startswith(("gpt-5", "o1", "o3", "o4")):
            return "max_completion_tokens"
        return "max_tokens"

    def _content_from_reasoning(self, reasoning_content: str) -> str:
        mode = self.settings.reasoning_content_mode.strip().lower()
        if mode in {"", "ignore"} or not reasoning_content:
            return ""
        if mode == "full":
            return reasoning_content.strip()
        if mode == "after_think":
            marker = "</think>"
            idx = reasoning_content.lower().rfind(marker)
            if idx >= 0:
                return reasoning_content[idx + len(marker):].strip()
            return reasoning_content.strip()
        raise ValueError(f"Unsupported MODEL_REASONING_CONTENT_MODE={self.settings.reasoning_content_mode!r}")

    def get_available_models(self) -> list[str]:
        response = requests.get(
            self._api_url("/models"),
            headers=self._headers(),
            timeout=min(30, self.settings.timeout_sec),
        )
        response.raise_for_status()
        data = response.json()

        aliases: list[str] = []
        if isinstance(data, dict):
            if isinstance(data.get("data"), list):
                for item in data["data"]:
                    model_id = item.get("id")
                    if isinstance(model_id, str):
                        aliases.append(model_id)
            if isinstance(data.get("models"), list):
                for item in data["models"]:
                    name = item.get("name") or item.get("model")
                    if isinstance(name, str):
                        aliases.append(name)

        out: list[str] = []
        seen: set[str] = set()
        for alias in aliases:
            if alias not in seen:
                out.append(alias)
                seen.add(alias)
        return out

    def resolve_model_name(self) -> str:
        if self._resolved_model_name:
            return self._resolved_model_name

        configured = self.settings.model_name.strip()
        if configured:
            self._resolved_model_name = configured
            return configured

        available = self.get_available_models()
        if available:
            self._resolved_model_name = available[0]
            return available[0]
        raise RuntimeError("No models are available from the configured model endpoint.")

    def _request_with_retries(self, payload: dict[str, Any]) -> requests.Response:
        errors: list[str] = []
        total = max(1, self.settings.max_retries)
        for idx in range(1, total + 1):
            try:
                response = requests.post(
                    self._api_url("/chat/completions"),
                    json=payload,
                    headers=self._headers(),
                    timeout=self.settings.timeout_sec,
                )
                if response.status_code >= 400:
                    body = self._trim(response.text or "<empty response>")
                    err = f"HTTP {response.status_code}: {body}"
                    if idx < total and self._is_retryable(response.status_code):
                        errors.append(err)
                        time.sleep(self.settings.retry_backoff_sec * idx)
                        continue
                    raise RuntimeError(err)
                return response
            except requests.Timeout:
                err = f"Timeout after {self.settings.timeout_sec}s"
                if idx < total:
                    errors.append(err)
                    time.sleep(self.settings.retry_backoff_sec * idx)
                    continue
                raise RuntimeError("; ".join(errors + [err]))
            except requests.RequestException as exc:
                err = f"Network error: {exc}"
                if idx < total:
                    errors.append(err)
                    time.sleep(self.settings.retry_backoff_sec * idx)
                    continue
                raise RuntimeError("; ".join(errors + [err]))
        raise RuntimeError("Unreachable retry state.")

    def chat(
        self,
        user_prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        *,
        journal=None,
        request_info: dict[str, Any] | None = None,
    ) -> str:
        messages = []
        final_system = system_prompt if system_prompt is not None else self.settings.system_prompt
        final_user_prompt = self._user_prompt_with_suffix(user_prompt)
        if final_system:
            messages.append({"role": "system", "content": final_system})
        messages.append({"role": "user", "content": final_user_prompt})

        model_name = self.resolve_model_name()
        token_param_name = self._token_param_name(model_name)
        payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            token_param_name: max_tokens,
        }

        prompt_dump = ""
        if final_system:
            prompt_dump += f"[system]\n{final_system}\n\n"
        prompt_dump += f"[user]\n{final_user_prompt}\n"

        token = journal.begin(request_info, prompt_dump) if journal is not None else None
        try:
            response = self._request_with_retries(payload)
            data = response.json()
            choice = data["choices"][0]
            message = choice.get("message", {})
            content = str(message.get("content") or "").strip()
            reasoning_content = str(message.get("reasoning_content") or "").strip()
            if not content:
                content = self._content_from_reasoning(reasoning_content)
            finish_reason = str(choice.get("finish_reason", "") or "")
            if finish_reason == "length":
                info = request_info or {}
                budget_env = str(info.get("budget_env") or "MODEL_MAX_TOKENS_*")
                error_text = (
                    f"Model response was truncated by max_tokens={max_tokens}. "
                    f"Increase {budget_env} for this stage."
                )
                if journal is not None and token is not None:
                    journal.finish(
                        token,
                        response_text=content,
                        error_text=error_text,
                        provider=self.provider,
                        model=model_name,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    token = None
                raise RuntimeError(error_text)
            if not content:
                raw_response = json_dumps_compact(data)
                detail = f"finish_reason={finish_reason or '<missing>'}; message_keys={sorted(message.keys())}"
                if reasoning_content:
                    detail += "; response contains reasoning_content but no assistant content"
                error_text = (
                    "Model returned empty assistant content. "
                    f"{detail}. Check model chat template/profile settings."
                )
                if journal is not None and token is not None:
                    journal.finish(
                        token,
                        response_text=raw_response,
                        error_text=error_text,
                        provider=self.provider,
                        model=model_name,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    token = None
                raise RuntimeError(error_text)
            if journal is not None and token is not None:
                journal.finish(
                    token,
                    response_text=content,
                    error_text=None,
                    provider=self.provider,
                    model=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            return content
        except Exception as exc:
            if journal is not None and token is not None:
                journal.finish(
                    token,
                    response_text=None,
                    error_text=str(exc),
                    provider=self.provider,
                    model=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            raise RuntimeError(
                f"Model request failed (provider={self.provider}, model={model_name}, base_url={self.settings.base_url}): {exc}"
            ) from exc

    def wait_until_ready(self) -> None:
        base = self.settings.base_url.lower()
        is_local_endpoint = "localhost" in base or "127.0.0.1" in base or "://llm" in base
        if self.settings.model_name and not is_local_endpoint:
            self.resolve_model_name()
            return

        deadline = time.time() + self.settings.ready_timeout_sec
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                available = self.get_available_models()
                if available:
                    configured = self.settings.model_name.strip()
                    if configured:
                        self._resolved_model_name = configured
                    else:
                        self._resolved_model_name = available[0]
                    return
            except Exception as exc:
                last_error = exc
            time.sleep(self.settings.ready_poll_sec)
        raise RuntimeError(f"Model endpoint did not become ready in time. Last error: {last_error}")


class LlamaCppClient(ModelClient):
    """Backward-compatible alias for local llama.cpp OpenAI-compatible endpoint."""


def create_model_client(settings: ModelSettings | None = None) -> ModelClient:
    cfg = settings or ModelSettings()
    provider = (cfg.provider or "openai_compatible").strip().lower()
    if provider in {"openai_compatible", "openai", "llama_cpp", "local"}:
        return ModelClient(cfg)
    raise ValueError(f"Unsupported MODEL_PROVIDER={cfg.provider!r}. Supported: openai_compatible, llama_cpp")
