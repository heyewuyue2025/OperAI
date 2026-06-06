"""E-Agent · 交易运营：转化漏斗、促销方案、CTA 优化（LLM + Mock 双路径）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..llm_json import chat_json_parse

MOCK: dict[str, Any] = {}


def validate(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    funnel = payload.get("funnel_steps") or []
    if len(funnel) < 3:
        issues.append("转化漏斗应至少包含 3 个阶段")
    promos = payload.get("promo_suggestions") or []
    for p in promos:
        if isinstance(p, dict) and not p.get("constraint"):
            issues.append(f"促销方案「{p.get('offer','')}」缺少约束条件")
    if not payload.get("cta_variants"):
        issues.append("缺少 CTA 变体")
    return issues


def _e_fallback(raw_input: str) -> dict[str, Any]:
    snippet = raw_input.strip().replace("\n", " ")[:160]
    return {
        "funnel_steps": [
            {"step": "触达", "description": f"围绕当前任务素材触达目标用户：{snippet}", "dropoff_risk": "目标人群或渠道不清会降低触达效率"},
            {"step": "理解", "description": "用户需要快速理解价值、行动方式和限制条件", "dropoff_risk": "信息结构不清会造成跳出"},
            {"step": "行动", "description": "将用户引导到明确的下一步", "dropoff_risk": "CTA 或转化入口不明确会造成流失"},
        ],
        "promo_suggestions": [{"offer": "按当前任务目标设计激励或权益", "constraint": f"必须基于真实素材与实际可交付能力：{snippet}"}],
        "cta_variants": ["查看详情", "了解下一步", "获取完整方案"],
        "_operai_fallback": "E-Agent LLM 不可用，已降级",
    }


def run_e(
    *, use_llm: bool, context: dict[str, Any],
    llm_cfg: dict[str, Any], root: Path | None = None,
) -> dict[str, Any]:
    _ = root
    if not use_llm:
        return _e_fallback(str(context.get("raw_input", "")))

    raw_input = str(context.get("raw_input", ""))
    upstream = context.get("upstream") or {}
    d_out = upstream.get("D") or {}
    c_out = upstream.get("C") or {}
    f_out = upstream.get("F") or {}

    system = (
        "你是电商/交易运营分析专家。根据素材和洞察，输出转化漏斗和促销方案。"
        "只输出合法 JSON：funnel_steps(对象数组, 每项 step+description+dropoff_risk)、"
        "promo_suggestions(对象数组, 每项 offer+constraint)、"
        "cta_variants(字符串数组, 不同场景的 CTA 文案)。"
        "促销约束必须明确——不得使用虚假紧迫感、不得承诺收益。"
    )
    payload: dict[str, Any] = {"raw_input": raw_input}
    if d_out:
        payload["d_insights"] = d_out.get("insights") or []
        payload["d_risk_flags"] = d_out.get("risk_flags") or []
    if c_out:
        payload["c_drafts_summary"] = {k: v[:200] for k, v in (c_out.get("drafts") or {}).items()}
    if f_out:
        payload["f_channel_scores"] = f_out.get("channel_scores") or []
    user = json.dumps(payload, ensure_ascii=False)

    try:
        return chat_json_parse(
            system=system, user=user, llm_cfg=llm_cfg,
            max_tokens=min(int(llm_cfg.get("max_tokens", 2048)), 1500),
        )
    except Exception:
        return _e_fallback(raw_input)


run_e_plugin = run_e
