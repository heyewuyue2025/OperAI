"""M-Agent · 市场运营：品牌定位、竞品分析、渠道组合（LLM + Mock 双路径）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..llm_json import chat_json_parse

MOCK: dict[str, Any] = {}


def validate(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not payload.get("positioning"):
        issues.append("缺少品牌定位")
    if not payload.get("channel_mix"):
        issues.append("缺少渠道组合建议")
    cms = payload.get("channel_mix") or []
    if len(cms) < 3:
        issues.append("渠道组合应至少覆盖 3 个渠道")
    return issues


def _m_fallback(raw_input: str) -> dict[str, Any]:
    snippet = raw_input.strip().replace("\n", " ")[:160]
    return {
        "positioning": f"基于当前素材的临时定位草稿，请人工复核：{snippet}",
        "competitive_notes": [{"topic": "竞争与替代方案", "note": "模型降级，请根据真实竞品、用户选择路径和渠道环境人工补充"}],
        "channel_mix": [{"channel": "综合渠道", "role": "承接核心信息与转化动作", "weight": "待定"}],
        "_operai_fallback": "M-Agent LLM 不可用，已降级",
    }


def run_m(
    *, use_llm: bool, context: dict[str, Any],
    llm_cfg: dict[str, Any], root: Path | None = None,
) -> dict[str, Any]:
    _ = root
    if not use_llm:
        return _m_fallback(str(context.get("raw_input", "")))

    raw_input = str(context.get("raw_input", ""))
    upstream = context.get("upstream") or {}
    d_out = upstream.get("D") or {}

    system = (
        "你是市场运营分析专家。根据素材和洞察，输出品牌定位和渠道策略。"
        "只输出合法 JSON：positioning(一句话定位)、competitive_notes(对象数组, 每项 topic+note)、"
        "channel_mix(对象数组, 每项 channel+role+weight)。"
        "风格专业克制，避免空泛表述。"
    )
    payload: dict[str, Any] = {"raw_input": raw_input}
    if d_out:
        payload["d_insights"] = d_out.get("insights") or []
        payload["d_angles"] = d_out.get("angles") or []
    user = json.dumps(payload, ensure_ascii=False)

    try:
        return chat_json_parse(
            system=system, user=user, llm_cfg=llm_cfg,
            max_tokens=min(int(llm_cfg.get("max_tokens", 2048)), 1200),
        )
    except Exception:
        return _m_fallback(raw_input)


run_m_plugin = run_m
