"""U-Agent: 用户运营 — 分群、生命周期、留存动作（LLM + Mock 双路径）。"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..llm_json import chat_json_parse

MOCK: dict[str, Any] = {
    "segments": [
        {"name": "高活跃在校生", "description": "近 7 天有互动或报名意向", "priority": "high"},
        {"name": "沉默围观", "description": "关注但未互动超过 14 天", "priority": "medium"},
    ],
    "lifecycle_stage": "activation",
    "retention_actions": [
        {"segment": "高活跃在校生", "action": "推送彩排花絮与志愿者入口", "channel": "wechat"},
        {"segment": "沉默围观", "action": "轻量话题互动 + 蹲后续提醒", "channel": "xhs"},
    ],
    "churn_risks": ["活动信息过载导致取关", "未回应评论引发负面体验"],
}

LIFECYCLE_STAGES = {"acquisition", "activation", "retention", "revenue", "referral"}


def validate(payload: dict[str, Any]) -> list[str]:
    """U-Agent 输出质量校验。"""
    issues: list[str] = []
    segments = payload.get("segments") or []
    if len(segments) < 2:
        issues.append("segments 数量应 ≥2")
    lifecycle = payload.get("lifecycle_stage", "")
    if lifecycle and lifecycle not in LIFECYCLE_STAGES:
        issues.append(f"lifecycle_stage '{lifecycle}' 不在五阶段范围内")
    actions = payload.get("retention_actions") or []
    for i, a in enumerate(actions):
        if isinstance(a, dict) and not a.get("segment"):
            issues.append(f"retention_actions[{i}] 缺少 segment 归属")
    return issues


# ── 非 LLM 领域逻辑 ──

def classify_segments(metrics: dict[str, Any], time_window_days: int = 30) -> list[dict[str, Any]]:
    """基于行为时间窗口的用户分群（非 LLM）。"""
    segments: list[dict[str, Any]] = []
    active = int(metrics.get("active_users", 0) or 0)
    silent = int(metrics.get("silent_users", 0) or 0)
    dormant = int(metrics.get("dormant_users", 0) or 0)
    total = active + silent + dormant or 1
    if active / total > 0.1:
        segments.append({"name": "高活跃用户", "description": f"近{time_window_days}天有互动", "priority": "high"})
    if silent / total > 0.1:
        segments.append({"name": "沉默用户", "description": f"近{time_window_days}天无互动但历史活跃", "priority": "medium"})
    if dormant / total > 0.1:
        segments.append({"name": "沉睡用户", "description": f"超过{time_window_days*2}天无任何行为", "priority": "low"})
    if not segments:
        segments.append({"name": "通用用户群", "description": "数据不足以分群，请人工补充", "priority": "high"})
    return segments


def determine_lifecycle(metrics: dict[str, Any]) -> str:
    """基于关键行为判定用户生命周期阶段（非 LLM）。"""
    has_purchase = bool(metrics.get("total_revenue") or metrics.get("has_purchase"))
    has_referral = bool(metrics.get("referral_count"))
    has_activation = bool(metrics.get("activation_done") or metrics.get("active_users"))
    days_since_reg = int(metrics.get("days_since_signup", 999) or 999)
    if has_referral:
        return "referral"
    if has_purchase:
        return "revenue"
    if has_activation:
        return "retention"
    if days_since_reg <= 7:
        return "activation"
    if days_since_reg > 7:
        return "acquisition"
    return "activation"


def detect_churn_risk(segments: list[dict[str, Any]], total: int = 0) -> list[str]:
    """基于分群占比量化流失风险（非 LLM）。"""
    risks: list[str] = []
    by_name = {s.get("name", ""): s for s in segments}
    if "流失预警" in by_name or "沉默用户" in by_name:
        risks.append("中等流失风险：沉默/预警用户占比偏高，建议48h内启动挽留触达")
    if "沉睡用户" in by_name:
        risks.append("高流失风险：沉睡用户占比较大，建议大促节点唤醒，日常触达ROI可能较低")
    if not risks:
        risks.append("当前分群未见明显流失信号，建议持续监测")
    return risks


def _u_fallback(raw_input: str) -> dict[str, Any]:
    snippet = raw_input.strip().replace("\n", " ")[:160]
    return {
        "segments": [
            {"name": "目标客群（模型降级）", "description": f"素材摘要：{snippet}", "priority": "high"},
        ],
        "lifecycle_stage": "activation",
        "retention_actions": [
            {"segment": "目标客群（模型降级）", "action": "请人工制定触达策略", "channel": "待定"}
        ],
        "churn_risks": ["请人工评估流失风险"],
        "_operai_fallback": "U-Agent LLM 不可用，已降级为应急分群草稿，请人工复核后使用",
    }


def run_u(
    *,
    use_llm: bool,
    context: dict[str, Any],
    llm_cfg: dict[str, Any],
    root: Path | None = None,
) -> dict[str, Any]:
    _ = root
    if not use_llm:
        return deepcopy(MOCK)

    raw_input = str(context.get("raw_input", ""))
    brand_voice = str(context.get("brand_voice", ""))
    upstream = context.get("upstream") or {}
    d_out = upstream.get("D") or {}

    system = (
        "你是用户运营分析助手。根据素材与洞察，输出用户分群与留存策略。"
        "只输出合法 JSON，键为 segments、lifecycle_stage、retention_actions、churn_risks。"
        "segments 为对象数组，每项含 name、description、priority（high/medium/low）。"
        "retention_actions 为对象数组，每项含 segment、action、channel。"
        "churn_risks 为字符串数组，描述可能的流失风险。"
    )
    payload: dict[str, Any] = {
        "raw_input": raw_input,
        "brand_voice": brand_voice,
    }
    if d_out:
        payload["d_insights"] = d_out.get("insights") or []
        payload["d_risk_flags"] = d_out.get("risk_flags") or []
    user = json.dumps(payload, ensure_ascii=False)

    try:
        return chat_json_parse(
            system=system,
            user=user,
            llm_cfg=llm_cfg,
            max_tokens=min(int(llm_cfg.get("max_tokens", 2048)), 1500),
        )
    except Exception:  # noqa: BLE001
        return _u_fallback(raw_input)


run_u_plugin = run_u
