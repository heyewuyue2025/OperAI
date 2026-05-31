"""S-Agent · 社群运营：社群动作、KOL策略、互动话术（LLM + Mock 双路径）。"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..llm_json import chat_json_parse

MOCK: dict[str, Any] = {
    "community_actions": [
        {"action": "发布彩排节目投票", "timing": "活动前 10 天", "goal": "提升参与感与社群黏性"},
        {"action": "志愿者答疑快闪群", "timing": "活动前 3-7 天", "goal": "降低现场不确定性，建立信任"},
        {"action": "活动后 UGC 征集", "timing": "活动后 1-3 天", "goal": "沉淀真实口碑素材，为下次活动蓄水"},
        {"action": "铁粉专属预告", "timing": "活动前 24h", "goal": "回馈高频互动用户，强化归属感"},
    ],
    "kol_hints": [
        {"profile": "校园音乐社团账号", "approach": "共创彩排花絮，强调「学生主办」叙事"},
        {"profile": "本地生活/探店博主", "approach": "实地踩点短评，突出安全与包容氛围"},
        {"profile": "校友圈意见领袖", "approach": "以「回母校看看」切入，覆盖已毕业校友群体"},
    ],
    "engagement_scripts": [
        {"scenario": "评论询问时间地点", "script": "场次以正文为准，评论区置顶 FAQ 已更新～蹲后续记得点关注"},
        {"scenario": "质疑安全保障", "script": "现场配备秩序志愿者与无酒精友好标识，具体措施见安全公告链接。"},
        {"scenario": "询问报名条件", "script": "面向全校师生及校友，志愿者报名不限年级，详见公众号菜单栏～"},
        {"scenario": "负面情绪宣泄", "script": "感谢关注。如有具体问题可私信，我们会尽快核实并反馈。"},
    ],
}


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
        "community_actions": [{"action": "请人工策划", "timing": "待定", "goal": "模型降级"}],
        "kol_hints": [{"profile": "待人工匹配", "approach": f"素材摘要：{snippet}"}],
        "engagement_scripts": [{"scenario": "通用回复", "script": "感谢关注，我们将尽快回复。"}],
        "_operai_fallback": "S-Agent LLM 不可用，已降级",
    }


def run_s(
    *, use_llm: bool, context: dict[str, Any],
    llm_cfg: dict[str, Any], root: Path | None = None,
) -> dict[str, Any]:
    _ = root
    if not use_llm:
        return deepcopy(MOCK)

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
