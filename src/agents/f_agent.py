"""F-Agent: 流量运营 — 渠道评分、预算分配、转化优化（LLM + Mock 双路径）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..llm_json import chat_json_parse

MOCK: dict[str, Any] = {}


def validate(payload: dict[str, Any]) -> list[str]:
    """F-Agent 输出质量校验。"""
    issues: list[str] = []
    scores = payload.get("channel_scores") or []
    for s in scores:
        if isinstance(s, dict):
            sc = s.get("score", -1)
            if not (0 <= sc <= 100):
                issues.append(f"渠道 '{s.get('channel','?')}' 评分 {sc} 不在 0-100 范围内")
            if not s.get("rationale"):
                issues.append(f"渠道 '{s.get('channel','?')}' 缺少评分理由")
    alloc = payload.get("budget_allocation") or []
    total = sum(float(a.get("percent", 0)) for a in alloc if isinstance(a, dict))
    if alloc and abs(total - 100) > 5:
        issues.append(f"预算分配总和 {total}%，偏离 100% 超过 5pp")
    if alloc:
        max_pct = max(float(a.get("percent", 0)) for a in alloc if isinstance(a, dict))
        if max_pct > 50:
            issues.append(f"单个渠道占比 {max_pct}% 超过 50%，风险过于集中")
    return issues


# ── 非 LLM 领域逻辑 ──

def score_channels(
    channels: list[dict[str, Any]],
    weights: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """加权多因子渠道评分（非 LLM）。
    因子：历史ROI(0.3) + 目标人群匹配(0.25) + 成本效率(0.2) + 规模(0.15) + 执行复杂度(0.1)
    """
    w = weights or {"roi": 0.30, "audience_match": 0.25, "cost_efficiency": 0.20, "scale": 0.15, "complexity": 0.10}
    results: list[dict[str, Any]] = []
    for ch in channels:
        name = str(ch.get("channel", "?"))
        roi_s = min(float(ch.get("roi_score", 50) or 50), 100)
        aud_s = min(float(ch.get("audience_match", 50) or 50), 100)
        cost_s = min(float(ch.get("cost_efficiency", 50) or 50), 100)
        scale_s = min(float(ch.get("scale", 50) or 50), 100)
        comp_s = 100 - min(float(ch.get("complexity", 50) or 50), 100)  # 越低越好
        score = round(
            roi_s * w["roi"] + aud_s * w["audience_match"] + cost_s * w["cost_efficiency"]
            + scale_s * w["scale"] + comp_s * w["complexity"]
        )
        results.append({"channel": name, "score": min(score, 100),
                         "rationale": f"ROI={roi_s}, 匹配={aud_s}, 成本效率={cost_s}, 规模={scale_s}, 易执行={comp_s}"})
    return results


def normalize_budget(scores: list[dict[str, Any]], total_budget: float) -> list[dict[str, Any]]:
    """基于评分归一化预算分配（非 LLM）。单渠道 ≤50%，实验 ≥10%。"""
    total_score = sum(s.get("score", 0) for s in scores) or 1
    allocations: list[dict[str, Any]] = []
    for s in scores:
        pct = round(s.get("score", 0) / total_score * 90)  # 留 10% 给实验
        allocations.append({"channel": s["channel"], "percent": min(pct, 50)})
    # 补实验预算
    allocated = sum(a["percent"] for a in allocations)
    if allocated < 100:
        allocations.append({"channel": "实验/新渠道", "percent": 100 - allocated})
    return allocations


def _f_fallback(raw_input: str) -> dict[str, Any]:
    snippet = raw_input.strip().replace("\n", " ")[:160]
    return {
        "channel_scores": [
            {"channel": "weibo", "score": 65, "rationale": "模型降级，需结合目标用户和内容形态人工评估"},
            {"channel": "wechat", "score": 65, "rationale": "模型降级，适合承载完整说明但需人工确认"},
            {"channel": "xhs", "score": 65, "rationale": "模型降级，需确认是否适合本次任务的场景化表达"},
        ],
        "budget_allocation": [{"channel": "weibo", "percent": 30}, {"channel": "wechat", "percent": 30}, {"channel": "xhs", "percent": 30}, {"channel": "实验/新渠道", "percent": 10}],
        "conversion_hints": [f"基于素材摘要先人工确认核心转化目标：{snippet}"],
        "_operai_fallback": "F-Agent LLM 不可用，已降级为应急流量分配草稿，请人工复核后使用",
    }


def run_f(
    *,
    use_llm: bool,
    context: dict[str, Any],
    llm_cfg: dict[str, Any],
    root: Path | None = None,
) -> dict[str, Any]:
    _ = root
    if not use_llm:
        return _f_fallback(str(context.get("raw_input", "")))

    raw_input = str(context.get("raw_input", ""))
    platforms = context.get("platforms") or ["weibo", "wechat", "xhs"]
    upstream = context.get("upstream") or {}
    d_out = upstream.get("D") or {}
    u_out = upstream.get("U") or {}

    system = (
        "你是流量与渠道运营分析专家。根据素材、洞察与用户分群，评估渠道效率并给出预算分配建议。"
        "只输出合法 JSON，键为 channel_scores、budget_allocation、conversion_hints。"
        "channel_scores 为对象数组，每项含 channel、score（0-100）、rationale。"
        "budget_allocation 为对象数组，每项含 channel、percent（总和应为 100）。"
        "conversion_hints 为字符串数组，给出提升转化的具体建议。"
    )

    payload: dict[str, Any] = {"raw_input": raw_input, "platforms": platforms}
    if d_out:
        payload["d_insights"] = d_out.get("insights") or []
        payload["d_risk_flags"] = d_out.get("risk_flags") or []
    if u_out:
        payload["u_segments"] = u_out.get("segments") or []
    user = json.dumps(payload, ensure_ascii=False)

    try:
        return chat_json_parse(
            system=system,
            user=user,
            llm_cfg=llm_cfg,
            max_tokens=min(int(llm_cfg.get("max_tokens", 2048)), 1500),
        )
    except Exception:  # noqa: BLE001
        return _f_fallback(raw_input)


run_f_plugin = run_f
