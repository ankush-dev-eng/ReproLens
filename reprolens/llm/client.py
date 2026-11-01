"""OpenRouter LLM client with retry backoff, Pydantic validation, and caching."""

import hashlib
import json
import logging
import random
import re
import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from reprolens.config import Config
from reprolens.db import Database
from reprolens.models import LLMCall

logger = logging.getLogger("reprolens.llm")

T = TypeVar("T", bound=BaseModel)

JSON_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*([\s\S]*?)\s*```$", re.MULTILINE)


def strip_json_fences(text: str) -> str:
    """Strip markdown code block fences if present."""
    text_clean = text.strip()
    match = JSON_FENCE_PATTERN.search(text_clean)
    if match:
        return match.group(1).strip()
    if text_clean.startswith("```") and text_clean.endswith("```"):
        lines = text_clean.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[1:-1]).strip()
    return text_clean


def redact_api_key(key: str) -> str:
    """Safely redact API key for logging."""
    if not key or len(key) < 10:
        return "[REDACTED]"
    return f"{key[:4]}...{key[-4:]}"


class OpenRouterClient:
    """Client for OpenRouter API with retries, caching, and schema enforcement."""

    ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_sec: float = 60.0,
        enable_cache: bool | None = None,
        db: Database | None = None,
    ) -> None:
        self.api_key = api_key or Config.OPENROUTER_API_KEY
        self.model = model or Config.MODEL
        self.timeout_sec = timeout_sec
        self.enable_cache = enable_cache if enable_cache is not None else Config.CACHE_LLM
        self.db = db or Database()

    def _compute_cache_key(
        self, model: str, system_prompt: str, user_prompt: str, temperature: float
    ) -> str:
        payload = f"{model}|{system_prompt}|{user_prompt}|{temperature}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
        temperature: float = 0.2,
        investigation_id: str | None = None,
        max_retries: int = 3,
    ) -> T:
        """Call OpenRouter, parse JSON response, and validate against Pydantic schema."""
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is not configured. "
                "Please configure OPENROUTER_API_KEY in .env or Streamlit secrets."
            )

        cache_key = self._compute_cache_key(self.model, system_prompt, user_prompt, temperature)

        # 1. Check local cache
        if self.enable_cache:
            cached_data = self.db.get_cached_llm(cache_key)
            if cached_data is not None:
                try:
                    return schema.model_validate(cached_data)
                except ValidationError:
                    pass

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/ankush-dev-eng/ReproLens",
            "X-Title": "ReproLens",
        }

        attempt = 0
        current_user_prompt = user_prompt

        while attempt < max_retries:
            attempt += 1
            start_time = time.monotonic()

            req_body = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": current_user_prompt},
                ],
                "temperature": temperature,
                "response_format": {"type": "json_object"},
            }

            try:
                with httpx.Client(timeout=self.timeout_sec) as client:
                    resp = client.post(self.ENDPOINT, headers=headers, json=req_body)

                latency = time.monotonic() - start_time

                # Handle Auth Errors (Never retry)
                if resp.status_code in (401, 403):
                    raise RuntimeError(
                        f"OpenRouter Authentication Error ({resp.status_code}): Invalid or unauthorized API key."
                    )

                # Handle Rate Limits (429)
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    sleep_time = (
                        float(retry_after)
                        if retry_after and retry_after.isdigit()
                        else 2.0**attempt
                    )
                    sleep_time += random.uniform(0.1, 0.5)
                    time.sleep(sleep_time)
                    continue

                if resp.status_code >= 500:
                    time.sleep(2.0**attempt + random.uniform(0.1, 0.5))
                    continue

                resp.raise_for_status()
                data = resp.json()

                # Extract tokens and usage
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
                cost_usd = usage.get("total_cost")  # OpenRouter usage provides cost if available

                # Audit log LLM call
                self.db.save_llm_call(
                    LLMCall(
                        investigation_id=investigation_id,
                        model=self.model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        cost_usd=cost_usd,
                        latency_sec=latency,
                    )
                )

                choices = data.get("choices", [])
                if not choices:
                    raise RuntimeError("Malformed OpenRouter response: choices list is empty.")

                raw_content = choices[0].get("message", {}).get("content", "")
                clean_json_str = strip_json_fences(raw_content)

                try:
                    parsed_dict = json.loads(clean_json_str)
                    validated_obj = schema.model_validate(parsed_dict)

                    # Save to cache
                    if self.enable_cache:
                        self.db.set_cached_llm(cache_key, parsed_dict)

                    return validated_obj

                except (json.JSONDecodeError, ValidationError) as val_err:
                    # One corrective re-prompt allowed
                    if attempt < max_retries:
                        current_user_prompt = (
                            f"{user_prompt}\n\n"
                            f"CORRECTION REQUIRED: Your previous response failed schema validation with error:\n"
                            f"{val_err}\n"
                            f"Please provide ONLY valid JSON strictly adhering to the schema."
                        )
                        continue
                    raise RuntimeError(
                        f"Failed to obtain valid JSON conforming to {schema.__name__}: {val_err}\nRaw output: {raw_content[:500]}"
                    ) from val_err

            except httpx.TimeoutException as e:
                if attempt >= max_retries:
                    raise RuntimeError(
                        f"OpenRouter call timed out after {max_retries} attempts."
                    ) from e
                time.sleep(2.0**attempt)

        raise RuntimeError(
            f"Failed to generate structured response from OpenRouter after {max_retries} attempts."
        )


class FakeLLM:
    """Mock LLM client for deterministic tests and offline execution."""

    def __init__(self, responses: dict[str, dict[str, Any]] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[dict[str, Any]] = []

    def set_response(self, keyword: str, response_dict: dict[str, Any]) -> None:
        self.responses[keyword] = response_dict

    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
        temperature: float = 0.2,
        investigation_id: str | None = None,
        max_retries: int = 3,
    ) -> T:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "schema": schema.__name__,
            }
        )

        for kw, resp in self.responses.items():
            if kw.lower() in user_prompt.lower() or kw.lower() in system_prompt.lower():
                return schema.model_validate(resp)

        # Fallback default matching schema
        if hasattr(schema, "model_construct"):
            # Construct empty or minimal valid object
            try:
                return schema()
            except Exception:
                pass

        raise ValueError(
            f"FakeLLM has no scripted response matching prompt with schema {schema.__name__}. "
            f"Prompt snippet: {user_prompt[:200]}"
        )
