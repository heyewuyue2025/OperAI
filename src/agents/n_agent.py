"""N-Agent · Rule-First : 渠道运营 — 排期、标签、分平台适配。

领域逻辑（非 LLM）:
  1. 平台最优发布时间窗口（硬编码行业数据，不靠 LLM 猜）
  2. 平台规则注入（字符限制、标签规范、首评引导模板）
  3. 跨平台排期冲突检测
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..llm_json import chat_json_parse
from ..platform_rules import rules_for_platforms

# 最优发布时间窗口（行业基准数据，非 LLM）
OPTIMAL_WINDOWS: dict[str, str] = {
    "weibo": "周二/周四 18:30-21:00（互动高峰）",
    "wechat": "周日 20:00（长阅读窗口）",
    "xhs": "周五 19:00-22:00（社区活跃）",
}

N_FALLBACK: dict[str, Any] = {
    "schedule_suggestions": [
        {"platform": "weibo", "window": OPTIMAL_WINDOWS["weibo"], "reason": "互动高峰"},
        {"platform": "wechat", "window": OPTIMAL_WINDOWS["wechat"], "reason": "长阅读窗口"},
        {"platform": "xhs", "window": OPTIMAL_WINDOWS["xhs"], "reason": "社区活跃"},
    ],
    "hashtags": ["#校园音乐节", "#学生主办"],
    "platform_notes": {
        "weibo": "140字内为主；首评可放链接引导。",
        "wechat": "标题克制；关键信息用列表。",
        "xhs": "适度emoji；避免夸大功效。",
    },
    "first_comment_suggestions": [
        {"platform": "weibo", "text": "详情见评论区置顶～"},
        {"platform": "xhs", "text": "想蹲后续的留言告诉我想看什么～"},
    ],
}


def validate(payload: dict[str, Any]) -> list[str]:
    """验证 N-Agent 输出质量。"""
    issues: list[str] = []
    sched = payload.get("schedule_suggestions") or []
    platforms_seen: set[str] = set()
    for s in sched:
        plat = str(s.get("platform", ""))
        if plat in platforms_seen:
            issues.append(f"平台「{plat}」排期重复")
        platforms_seen.add(plat)
    tags = payload.get("hashtags") or []
    if not tags:
        issues.append("hashtags 为空")
    elif len(tags) > 5:
        issues.append(f"hashtags 数量 {len(tags)} > 5，建议精简")
    return issues


def run_n(
    *, use_llm: bool, c_out: dict[str, Any], llm_cfg: dict[str, Any],
    platforms: list[str] | None = None, root: Path | None = None,
) -> dict[str, Any]:
    if not use_llm:
        out = deepcopy(N_FALLBACK)
        # 注入非 LLM 窗口数据
        out["_optimal_windows"] = {p: OPTIMAL_WINDOWS.get(p, "") for p in (platforms or [])}
        return out

    system = (
        "你是渠道运营。根据 drafts 给出分发策略。只输出 JSON："
        "schedule_suggestions(数组, 每项platform/window/reason), "
        "hashtags(字符串数组), platform_notes(对象, 键为平台), "
        "first_comment_suggestions(数组, 每项platform/text)。"
    )
    plats = platforms or list((c_out.get("drafts") or {}).keys())
    payload: dict[str, Any] = {
        "c_agent": c_out,
        "optimal_windows": {p: OPTIMAL_WINDOWS.get(p, "") for p in plats},
    }
    if root is not None:
        payload["platform_rules"] = rules_for_platforms(root, plats)
    user = json.dumps(payload, ensure_ascii=False)

    try:
        out = chat_json_parse(
            system=system, user=user, llm_cfg=llm_cfg,
            max_tokens=min(int(llm_cfg.get("max_tokens", 2048)), 1500),
        )
        out["_optimal_windows"] = payload["optimal_windows"]
        return out
    except Exception:
        out = deepcopy(N_FALLBACK)
        out["_operai_fallback"] = "LLM 不可用，已降级"
        return out


def run_n_plugin(*, use_llm: bool, context: dict[str, Any], llm_cfg: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    upstream = context.get("upstream") or {}
    c_out = upstream.get("C") or {}
    platforms = context.get("platforms")
    return run_n(use_llm=use_llm, c_out=c_out, llm_cfg=llm_cfg, platforms=platforms, root=root)
