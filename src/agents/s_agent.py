"""S-Agent · 社群运营：社群动作、KOL策略、互动话术（LLM + Mock 双路径）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..llm_json import chat_json_parse

MOCK: dict[str, Any] = {}


def validate(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    actions = payload.get("community_actions") or []
    if len(actions) < 3:
        issues.append(f"community_actions 至少 3 个，当前 {len(actions)}")
    for a in actions:
        if isinstance(a, dict):
            if not a.get("timing"):
                issues.append(f"社群动作「{a.get('action','?')}」缺少 timing")
            if not a.get("goal"):
                issues.append(f"社群动作「{a.get('action','?')}」缺少 goal")
    if not payload.get("kol_hints"):
        issues.append("缺少 KOL 推荐")
    return issues


def _s_fallback(raw_input: str) -> dict[str, Any]:
    snippet = raw_input.strip().replace("\n", " ")[:160]
    return {
        "community_actions": [{"action": "围绕当前任务建立互动主题", "timing": "待定", "goal": f"让用户理解任务价值并产生有效反馈：{snippet}"}],
        "kol_hints": [{"profile": "与目标用户重合的内容创作者或社群节点", "approach": "基于真实素材共创内容，避免脱离任务场景"}],
        "engagement_scripts": [{"scenario": "通用回复", "script": "感谢关注，我们会根据真实信息持续更新。"}],
        "_operai_fallback": "S-Agent LLM 不可用，已降级",
    }


def run_s(
    *, use_llm: bool, context: dict[str, Any],
    llm_cfg: dict[str, Any], root: Path | None = None,
) -> dict[str, Any]:
    _ = root
    if not use_llm:
        return _s_fallback(str(context.get("raw_input", "")))

    raw_input = str(context.get("raw_input", ""))
    upstream = context.get("upstream") or {}
    d_out = upstream.get("D") or {}
    u_out = upstream.get("U") or {}
    c_out = upstream.get("C") or {}

    system = (
        "你是社群运营专家。根据素材和上游产出，制定社群运营方案。"
        "只输出合法 JSON：community_actions(对象数组, 每项 action+timing+goal)、"
        "kol_hints(对象数组, 每项 profile+approach)、"
        "engagement_scripts(对象数组, 每项 scenario+script)。"
        "话术需自然、有温度，避免官方腔。"
    )
    payload: dict[str, Any] = {"raw_input": raw_input}
    if d_out:
        payload["d_insights"] = d_out.get("insights") or []
    if u_out:
        payload["u_segments"] = u_out.get("segments") or []
    if c_out:
        payload["c_drafts"] = {k: v[:200] for k, v in (c_out.get("drafts") or {}).items()}
    user = json.dumps(payload, ensure_ascii=False)

    try:
        return chat_json_parse(
            system=system, user=user, llm_cfg=llm_cfg,
            max_tokens=min(int(llm_cfg.get("max_tokens", 2048)), 1500),
        )
    except Exception:
        return _s_fallback(raw_input)


run_s_plugin = run_s
