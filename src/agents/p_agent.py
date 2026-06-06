"""P-Agent · 产品运营：功能洞察、UX 信号、迭代建议（LLM + Mock 双路径）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..llm_json import chat_json_parse

MOCK: dict[str, Any] = {}


def validate(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    fis = payload.get("feature_insights") or []
    for fi in fis:
        if isinstance(fi, dict) and not fi.get("feature"):
            issues.append("feature_insight 缺少 feature 字段")
        if isinstance(fi, dict) and not fi.get("insight"):
            issues.append("feature_insight 缺少 insight 字段")
    if not payload.get("iteration_hints"):
        issues.append("缺少迭代建议")
    return issues


def _p_fallback(raw_input: str) -> dict[str, Any]:
    snippet = raw_input.strip().replace("\n", " ")[:160]
    return {
        "feature_insights": [{"feature": "降级", "insight": f"模型不可用，请人工分析。素材：{snippet}"}],
        "ux_signals": ["请人工收集 UX 反馈"],
        "iteration_hints": [{"priority": "P1", "recommendation": "模型降级，请人工评估迭代优先级"}],
        "_operai_fallback": "P-Agent LLM 不可用，已降级",
    }


def run_p(
    *, use_llm: bool, context: dict[str, Any],
    llm_cfg: dict[str, Any], root: Path | None = None,
) -> dict[str, Any]:
    _ = root
    if not use_llm:
        return _p_fallback(str(context.get("raw_input", "")))

    raw_input = str(context.get("raw_input", ""))
    upstream = context.get("upstream") or {}
    d_out = upstream.get("D") or {}

    system = (
        "你是产品运营分析专家。根据素材和洞察，输出产品功能分析。"
        "只输出合法 JSON：feature_insights(对象数组, 每项 feature+insight+metric_ref)、"
        "ux_signals(字符串数组)、iteration_hints(对象数组, 每项 priority(P0/P1/P2)+recommendation)。"
    )
    payload: dict[str, Any] = {"raw_input": raw_input}
    if d_out:
        payload["d_insights"] = d_out.get("insights") or []
        payload["d_risk_flags"] = d_out.get("risk_flags") or []
    user = json.dumps(payload, ensure_ascii=False)

    try:
        return chat_json_parse(
            system=system, user=user, llm_cfg=llm_cfg,
            max_tokens=min(int(llm_cfg.get("max_tokens", 2048)), 1200),
        )
    except Exception:
        return _p_fallback(raw_input)


run_p_plugin = run_p
