"""C-Agent · LLM-Augmented : 多平台内容生成。

领域逻辑（非 LLM）:
  1. platform_rules 注入 — 微博140字、小红书emoji规范、公众号排版
  2. 输出校验 — 每篇 draft 长度检查、敏感平台规则合规
  3. 合规标注自动补全 — 平台规则与风险提示检查
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..llm_json import chat_json_parse
from ..platform_rules import rules_for_platforms

# 平台硬限制（非 LLM 校验用）
PLATFORM_LIMITS = {"weibo": 2000, "wechat": 20000, "xhs": 1000, "bilibili": 2000, "douyin": 500, "kuaishou": 500}
_DRIFT_TERMS = ("投资", "股票", "基金", "理财", "收益", "本金", "持仓", "市场波动", "短期情绪")

MOCK: dict[str, Any] = {}


def validate(payload: dict[str, Any], *, pack_id: str = "") -> list[str]:
    """验证 C-Agent 输出质量（非 LLM 规则）。"""
    issues: list[str] = []
    drafts = payload.get("drafts") or {}
    if not drafts:
        issues.append("drafts 为空")
    for plat, text in drafts.items():
        limit = PLATFORM_LIMITS.get(plat)
        if limit and len(str(text)) > limit:
            issues.append(f"「{plat}」文案 {len(text)} 字，超出平台限制 {limit} 字")
    return issues


# ── 非 LLM 领域逻辑 ──

def check_cross_platform_consistency(drafts: dict[str, str]) -> list[str]:
    """非 LLM：检查跨平台核心数字/事实一致性。"""
    import re as _re
    issues: list[str] = []
    texts = list(drafts.values())
    if len(texts) < 2:
        return issues
    # 提取所有数字
    nums_per_plat: dict[str, set[str]] = {}
    for plat, text in drafts.items():
        nums_per_plat[plat] = set(_re.findall(r"\d{1,4}(?:\.\d+)?%?", text))
    all_nums: set[str] = set()
    for ns in nums_per_plat.values():
        all_nums |= ns
    for num in all_nums:
        holders = [p for p, ns in nums_per_plat.items() if num in ns]
        if 0 < len(holders) < len(drafts):
            missing = [p for p in drafts if p not in holders]
            issues.append(f"数字「{num}」出现在 {', '.join(holders)}，但未在 {', '.join(missing)} 中出现")
    return issues


def check_content_ratio(plan: list[dict[str, str]]) -> dict[str, Any]:
    """非 LLM：检查 4-1-1 内容比例。promotional > 30% 则警告。"""
    total = len(plan) or 1
    promo = sum(1 for p in plan if str(p.get("type", "")).lower() in ("promo", "promotional", "推广", "促销"))
    ratio = promo / total
    return {
        "promotional_ratio": f"{ratio:.0%}",
        "warning": "推广内容占比超 30%，建议增加价值/教育型内容" if ratio > 0.3 else None,
    }


def _fallback_from_task(raw_input: str, platforms: list[str]) -> dict[str, Any]:
    """当 LLM 串题时，用原始材料生成一个保守、可复核的应急成稿。"""
    material = " ".join(raw_input.strip().split())
    focus = material[:120] or "当前运营任务"
    selected = platforms or ["weibo", "wechat", "xhs"]
    labels = {
        "weibo": f"{focus}。我们会持续同步关键信息、进展和参与方式，欢迎关注后续更新。",
        "wechat": f"本次内容将围绕「{focus}」展开，重点说明背景、价值、执行节奏和用户需要知道的关键信息。",
        "xhs": f"{focus}\n把重点整理给你：背景、亮点、适合谁、下一步怎么参与。",
        "bilibili": f"围绕「{focus}」做一期完整说明：为什么做、怎么推进、有哪些关键节点和注意事项。",
        "douyin": f"{focus}。先看重点，再看行动入口，后续会继续更新执行进展。",
        "kuaishou": f"{focus}。这次先把重点讲清楚，后面持续更新真实进展。",
    }
    return {
        "drafts": {plat: labels.get(plat, f"{focus}。后续将持续更新。") for plat in selected},
        "title_variants": ["先把重点讲清楚", "这次运营任务怎么推进", "用户最需要知道的几件事"],
        "short_video_script": f"大家好，这次我们主要想讲清楚：{focus}。后续会按节奏同步进展、参与方式和注意事项。",
        "compliance_notes": ["已触发防串题保护：输出仅基于原始任务材料生成，请人工终审。"],
        "_operai_guardrail": "topic_drift_fallback",
    }


def _contains_topic_drift(payload: dict[str, Any], raw_input: str) -> bool:
    source = raw_input or ""
    if any(term in source for term in _DRIFT_TERMS):
        return False
    drafts = payload.get("drafts") or {}
    joined = " ".join(str(text) for text in drafts.values())
    return any(term in joined for term in _DRIFT_TERMS)


def run_c(
    *, use_llm: bool, d_out: dict[str, Any], platforms: list[str],
    raw_input: str = "", brand_voice: str = "",
    llm_cfg: dict[str, Any], root: Path | None = None,
) -> dict[str, Any]:
    if not use_llm:
        return _fallback_from_task(raw_input, platforms)

    system = (
        "你是给公司运营团队使用的内容运营专家。必须严格根据 raw_input、brand_voice、d_agent.evidence_spans、"
        "d_agent.insights 和 d_agent.angles 写多平台文案。"
        "如果 d_agent 与 raw_input 冲突，以 raw_input 为准。"
        "禁止改写成金融、投资、理财、医疗、教育培训等用户未要求的主题；禁止加入 raw_input 没有出现的产品、行业、场景。"
        "只输出 JSON："
        "drafts(键为平台代码，值为文案), title_variants(字符串数组3条), "
        "short_video_script(30-60秒口播稿), compliance_notes(合规说明数组)。"
        "每个平台文案都必须保留原始材料中的核心产品/活动/用户目标。风格克制可信，遵守 risk_flags。"
    )
    payload: dict[str, Any] = {
        "raw_input": raw_input,
        "brand_voice": brand_voice,
        "d_agent": d_out,
        "platforms": platforms,
    }
    if root is not None:
        payload["platform_rules"] = rules_for_platforms(root, platforms)
    user = json.dumps(payload, ensure_ascii=False)

    try:
        out = chat_json_parse(
            system=system, user=user, llm_cfg=llm_cfg,
            max_tokens=min(int(llm_cfg.get("max_tokens", 2048)), 1400),
        )
        if _contains_topic_drift(out, raw_input):
            return _fallback_from_task(raw_input, platforms)
        return out
    except Exception:
        out = _fallback_from_task(raw_input, platforms)
        out["_operai_fallback"] = "LLM 不可用，已降级为基于原始材料的应急成稿"
        return out


def run_c_plugin(*, use_llm: bool, context: dict[str, Any], llm_cfg: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    upstream = context.get("upstream") or {}
    d_out = upstream.get("D") or {}
    platforms = context.get("platforms") or ["weibo", "wechat", "xhs"]
    return run_c(
        use_llm=use_llm,
        d_out=d_out,
        platforms=platforms,
        raw_input=str(context.get("raw_input", "")),
        brand_voice=str(context.get("brand_voice", "")),
        llm_cfg=llm_cfg,
        root=root,
    )
