"""N-Agent · Rule-First : 渠道运营 — 排期、标签、分平台适配。

领域逻辑（非 LLM）:
  1. 平台最优发布时间窗口（硬编码行业数据，不靠 LLM 猜）
  2. 平台规则注入（字符限制、标签规范、首评引导模板）
  3. 跨平台排期冲突检测
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..llm_json import chat_json_parse
from ..platform_rules import rules_for_platforms

# 最优发布时间窗口（行业基准数据，非 LLM）
OPTIMAL_WINDOWS: dict[str, str] = {
    "weibo": "周二/周四 18:30-21:00（互动高峰）",
    "wechat": "周日 20:00（长阅读窗口）",
    "xhs": "周五 19:00-22:00（社区活跃）",
    "bilibili": "周五/周六 19:00-22:30（长视频观看窗口）",
    "douyin": "每日 12:00-13:30 或 19:00-22:00（短视频活跃）",
    "kuaishou": "每日 18:00-21:30（社区互动窗口）",
}

PLATFORM_NOTES: dict[str, str] = {
    "weibo": "短句和话题标签优先；首评可放链接引导。",
    "wechat": "标题克制；关键信息用列表，适合承载完整说明。",
    "xhs": "场景化表达，适度口语，避免夸大功效。",
    "bilibili": "适合筹备记录、幕后过程和较完整的视频说明。",
    "douyin": "开头三秒要直接给看点，适合短视频口播和花絮。",
    "kuaishou": "表达更生活化，适合连续更新和社区互动。",
}

N_FALLBACK: dict[str, Any] = {
    "schedule_suggestions": [
        {"platform": "weibo", "window": OPTIMAL_WINDOWS["weibo"], "reason": "互动高峰"},
        {"platform": "wechat", "window": OPTIMAL_WINDOWS["wechat"], "reason": "长阅读窗口"},
        {"platform": "xhs", "window": OPTIMAL_WINDOWS["xhs"], "reason": "社区活跃"},
    ],
    "hashtags": ["#运营方案", "#内容发布"],
    "platform_notes": {key: PLATFORM_NOTES[key] for key in ("weibo", "wechat", "xhs")},
    "first_comment_suggestions": [
        {"platform": "weibo", "text": "关键信息可在评论区补充说明。"},
        {"platform": "xhs", "text": "欢迎在评论区补充你的问题或反馈。"},
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
        selected = platforms or ["weibo", "wechat", "xhs"]
        return {
            "schedule_suggestions": [
                {"platform": p, "window": OPTIMAL_WINDOWS.get(p, "按平台历史活跃数据选择"), "reason": "匹配平台活跃窗口"}
                for p in selected
            ],
            "hashtags": ["#运营方案", "#内容发布"],
            "platform_notes": {p: PLATFORM_NOTES.get(p, "按平台内容规范人工复核。") for p in selected},
            "first_comment_suggestions": [
                {"platform": p, "text": "根据本次任务材料补充关键信息和下一步入口。"} for p in selected[:2]
            ],
            "_optimal_windows": {p: OPTIMAL_WINDOWS.get(p, "") for p in selected},
            "_operai_fallback": "N-Agent 使用规则排期，未调用 LLM",
        }

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
        selected = plats or ["weibo", "wechat", "xhs"]
        return {
            "schedule_suggestions": [
                {"platform": p, "window": OPTIMAL_WINDOWS.get(p, "按平台历史活跃数据选择"), "reason": "LLM 不可用，使用规则排期"}
                for p in selected
            ],
            "hashtags": ["#运营方案", "#内容发布"],
            "platform_notes": {p: PLATFORM_NOTES.get(p, "按平台内容规范人工复核。") for p in selected},
            "first_comment_suggestions": [
                {"platform": p, "text": "根据本次任务材料补充关键信息和下一步入口。"} for p in selected[:2]
            ],
            "_optimal_windows": {p: OPTIMAL_WINDOWS.get(p, "") for p in selected},
            "_operai_fallback": "LLM 不可用，已降级为规则排期",
        }


def run_n_plugin(*, use_llm: bool, context: dict[str, Any], llm_cfg: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    upstream = context.get("upstream") or {}
    c_out = upstream.get("C") or {}
    platforms = context.get("platforms")
    return run_n(use_llm=use_llm, c_out=c_out, llm_cfg=llm_cfg, platforms=platforms, root=root)
