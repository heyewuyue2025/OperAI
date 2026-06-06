"""OpenAI-compatible chat completion; returns assistant text."""
from __future__ import annotations

import os
from typing import Any

from openai import OpenAI


def get_client() -> OpenAI | None:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return None
    base = os.getenv("OPENAI_BASE_URL") or None
    return OpenAI(api_key=key, base_url=base)


def chat_json(
    system: str,
    user: str,
    *,
    model: str,
    temperature: float,
    max_tokens: int,
    timeout: float,
) -> tuple[str, dict[str, int]]:
    client = get_client()
    if client is None:
        raise RuntimeError("OPENAI_API_KEY 未配置")
    request: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": timeout,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if model.lower().startswith("deepseek-v4"):
        request["extra_body"] = {"thinking": {"type": "disabled"}}
    resp = client.chat.completions.create(**request)
    choice = resp.choices[0].message
    if not choice or not choice.content:
        raise RuntimeError("模型返回空内容")
    usage: dict[str, int] = {}
    if resp.usage:
        usage = {
            "prompt_tokens": int(resp.usage.prompt_tokens or 0),
            "completion_tokens": int(resp.usage.completion_tokens or 0),
            "total_tokens": int(resp.usage.total_tokens or 0),
        }
    return choice.content.strip(), usage
