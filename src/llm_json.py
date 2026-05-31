"""LLM 文本 → JSON：多轮抽取 / 修复；失败时由调用方降级。"""
from __future__ import annotations

import json
import re
from typing import Any


def strip_markdown_fence(text: str) -> str:
    t = text.strip()
    if not t.startswith("```"):
        return t
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
    if t.rstrip().endswith("```"):
        t = t.rstrip()[:-3].strip()
    return t.strip()


def slice_outer_json_object(text: str) -> str:
    """从含前后废话的文本中切出最外层 `{ ... }` 片段（启发式）。"""
    s = text.find("{")
    e = text.rfind("}")
    if s == -1 or e == -1 or e <= s:
        raise ValueError("未找到 JSON 对象边界")
    return text[s : e + 1].strip()


def parse_json_object(text: str) -> dict[str, Any]:
    """依次尝试：去围栏 → 原样 → 大括号切片。"""
    candidates: list[str] = []
    t0 = text.strip()
    candidates.append(strip_markdown_fence(t0))
    candidates.append(t0)
    try:
        candidates.append(slice_outer_json_object(t0))
    except ValueError:
        pass
    seen: set[str] = set()
    last_err: Exception | None = None
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        try:
            out = json.loads(c)
            if not isinstance(out, dict):
                raise ValueError("根节点必须是 JSON 对象")
            return out
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            continue
    if last_err is None:
        raise ValueError("无法解析 JSON")
    raise ValueError(f"无法解析 JSON: {last_err}") from last_err


def chat_json_parse(
    *,
    system: str,
    user: str,
    llm_cfg: dict[str, Any],
    max_tokens: int,
) -> dict[str, Any]:
    """调用 LLM → 解析 JSON；失败则自动发起一次「仅输出 JSON」修复请求。"""
    from .llm_client import chat_json

    model = llm_cfg["model"]
    temperature = float(llm_cfg["temperature"])
    timeout = float(llm_cfg["timeout_seconds"])
    extra = int(llm_cfg.get("max_retries", 1))

    last_usage: dict[str, int] = {}

    def _call(sys: str, usr: str, mt: int) -> str:
        nonlocal last_usage
        text, usage = chat_json(
            sys,
            usr,
            model=model,
            temperature=temperature,
            max_tokens=mt,
            timeout=timeout,
        )
        if usage:
            last_usage = usage
        return text

    last_text = ""
    attempts = 1 + max(0, extra)
    last_err: Exception | None = None
    for i in range(attempts):
        try:
            if i == 0:
                last_text = _call(system, user, max_tokens)
            else:
                repair_sys = (
                    "你是 JSON 修复器。只输出一个合法 JSON 对象：不要 markdown、不要解释、不要前后缀。"
                )
                repair_user = (
                    "下列模型输出无法被 json.loads 解析。请推断原意图并输出**等价且合法**的 JSON。\n\n"
                    f"<<<\n{last_text[:12000]}\n>>>"
                )
                last_text = _call(repair_sys, repair_user, min(max_tokens + 512, 4096))
            out = parse_json_object(last_text)
            if last_usage:
                out["_llm_usage"] = last_usage
            return out
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            last_err = e
            continue
    raise ValueError(f"LLM JSON 解析失败（{attempts} 次尝试）: {last_err}") from last_err
