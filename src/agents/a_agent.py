"""A-Agent: 活动运营 — 战役计划、预算建议、ROI 预估（LLM + Mock 双路径）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..llm_json import chat_json_parse

MOCK: dict[str, Any] = {}


def validate(payload: dict[str, Any]) -> list[str]:
    """A-Agent 输出质量校验。"""
    issues: list[str] = []
    plan = payload.get("campaign_plan") or []
    if len(plan) < 2:
        issues.append("campaign_plan 应至少包含 2 个阶段（预热/爆发/收尾）")
    hints = payload.get("budget_hints") or []
    if len(hints) >= 2:
        # 多渠道时检查百分比范围是否大致涵盖 100%
        total_min = 0.0
        total_max = 0.0
        for h in hints:
            r = str(h.get("percent_range", ""))
            parts = r.replace("%", "").split("-")
            if len(parts) == 2:
                try:
                    total_min += float(parts[0].strip())
                    total_max += float(parts[1].strip())
                except ValueError:
                    pass
        if total_min > 120 or total_max < 80:
            issues.append(f"预算占比可能不合理：min={total_min}%, max={total_max}%")
    roi = payload.get("roi_estimate") or {}
    if isinstance(roi, dict) and not roi.get("assumptions"):
        issues.append("ROI 预估缺少 assumptions")
    return issues


# ── 非 LLM 领域逻辑 ──

def build_campaign_template() -> list[dict[str, Any]]:
    """基于行业标准模板生成三阶段战役框架（非 LLM）。"""
    return [
        {
            "phase": "预热期",
            "objective": "建立认知与期待",
            "tasks": ["核心信息梳理", "目标人群触达", "渠道预告"],
            "budget_ratio": "20%-30%",
        },
        {
            "phase": "爆发期",
            "objective": "集中转化",
            "tasks": ["多平台发布", "实时数据监控", "关键问题响应"],
            "budget_ratio": "50%-60%",
        },
        {
            "phase": "收尾期",
            "objective": "长尾收割 + 口碑沉淀",
            "tasks": ["结果复盘", "用户反馈回收", "后续动作建议"],
            "budget_ratio": "10%-20%",
        },
    ]


def calculate_roi_estimate(
    budget: float, expected_reach: int, historical_cvr: float, avg_order_value: float,
) -> dict[str, Any]:
    """基于非 LLM 公式计算 ROI 预估。"""
    if expected_reach <= 0 or avg_order_value <= 0:
        return {"summary": "数据不足，无法计算 ROI 预估", "assumptions": [], "confidence": "low"}
    expected_orders = expected_reach * historical_cvr
    expected_revenue = expected_orders * avg_order_value
    roi = expected_revenue / budget if budget > 0 else 0
    return {
        "summary": (
            f"预期触达 {expected_reach:,} 人，基于历史转化率 {historical_cvr:.1%}，"
            f"预计订单 {expected_orders:,.0f} 单，GMV ¥{expected_revenue:,.0f}，ROI {roi:.1f}x"
        ),
        "assumptions": [
            f"历史 CVR = {historical_cvr:.1%}",
            f"AOV = ¥{avg_order_value:,.0f}",
            f"预期触达 = {expected_reach:,}",
        ],
        "confidence": "medium" if historical_cvr > 0.01 else "low",
    }


def validate_budget_allocation(budget_hints: list[dict[str, Any]]) -> list[str]:
    """校验预算分配的合理性（非 LLM）。"""
    issues: list[str] = []
    if not budget_hints:
        return ["缺少预算分配建议"]
    total_min = 0.0
    total_max = 0.0
    for h in budget_hints:
        r = str(h.get("percent_range", "")).replace("%", "").split("-")
        if len(r) == 2:
            try:
                total_min += float(r[0].strip())
                total_max += float(r[1].strip())
            except ValueError:
                pass
    if abs(total_min - 100) > 15 or abs(total_max - 100) > 15:
        issues.append(f"预算范围总和偏差较大：min={total_min}%, max={total_max}%")
    return issues


def _a_fallback(raw_input: str) -> dict[str, Any]:
    snippet = raw_input.strip().replace("\n", " ")[:160]
    return {
        "campaign_plan": [
            {"phase": "准备", "objective": "澄清目标、受众、资源和约束", "tasks": ["整理任务材料", "确认目标平台", "定义成功指标"], "owner_agent": "D"},
            {"phase": "执行", "objective": "把方案发布到合适渠道并监控反馈", "tasks": ["生成核心内容", "安排发布节奏", "跟踪关键反馈"], "owner_agent": "C"},
            {"phase": "复盘", "objective": "沉淀结果、风险和下一步动作", "tasks": ["汇总数据表现", "标记风险与问题", "形成复盘建议"], "owner_agent": "N"},
        ],
        "budget_hints": [{"channel": "综合渠道", "suggestion": "根据本次任务目标和历史表现人工确认预算", "percent_range": "待定"}],
        "roi_estimate": {
            "summary": f"模型降级，基于素材摘要：{snippet}",
            "assumptions": ["请人工设定评估指标"],
            "confidence": "low",
        },
        "_operai_fallback": "A-Agent LLM 不可用，已降级为应急活动方案草稿，请人工复核后使用",
    }


def run_a(
    *,
    use_llm: bool,
    context: dict[str, Any],
    llm_cfg: dict[str, Any],
    root: Path | None = None,
) -> dict[str, Any]:
    _ = root
    if not use_llm:
        return _a_fallback(str(context.get("raw_input", "")))

    raw_input = str(context.get("raw_input", ""))
    upstream = context.get("upstream") or {}
    d_out = upstream.get("D") or {}
    u_out = upstream.get("U") or {}

    system = (
        "你是活动运营策划专家。根据素材、洞察与用户分群，输出活动战役方案。"
        "只输出合法 JSON，键为 campaign_plan、budget_hints、roi_estimate。"
        "campaign_plan 为对象数组，每项含 phase、objective、tasks（字符串数组）、owner_agent（建议协作的 agent_id）。"
        "budget_hints 为对象数组，每项含 channel、suggestion、percent_range（如 20%-30%）。"
        "roi_estimate 为对象，含 summary、assumptions（字符串数组）、confidence（low/medium/high）。"
    )
    payload: dict[str, Any] = {"raw_input": raw_input}
    if d_out:
        payload["d_insights"] = d_out.get("insights") or []
        payload["d_risk_flags"] = d_out.get("risk_flags") or []
    if u_out:
        payload["u_segments"] = u_out.get("segments") or []
        payload["u_lifecycle"] = u_out.get("lifecycle_stage", "")
    user = json.dumps(payload, ensure_ascii=False)

    try:
        return chat_json_parse(
            system=system,
            user=user,
            llm_cfg=llm_cfg,
            max_tokens=min(int(llm_cfg.get("max_tokens", 2048)), 1500),
        )
    except Exception:  # noqa: BLE001
        return _a_fallback(raw_input)


run_a_plugin = run_a
