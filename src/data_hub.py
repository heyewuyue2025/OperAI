"""统一数据基座 — D-Agent 的数据基础设施。

职责：
  1. 从 raw_input + structured_metrics 中提取和归一化所有指标
  2. 为所有 Agent 提供统一的数据查询接口
  3. 缓存最近一次提取结果，避免重复解析

这是 PRD §2 "D-Agent 是数据底座"的工程实现。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MetricSnapshot:
    """一次数据提取的快照。"""
    numbers: list[str] = field(default_factory=list)        # 所有数字/百分比
    amounts: list[str] = field(default_factory=list)         # 金额
    dates: list[str] = field(default_factory=list)           # 日期/时间
    entities: list[str] = field(default_factory=list)        # 实体（品牌/产品/人名）
    platforms: list[str] = field(default_factory=list)       # 平台
    raw_metrics: dict[str, Any] = field(default_factory=dict)  # 用户提交的 structured_metrics
    summary: str = ""  # 可供注入上下文的文本摘要


# 全局缓存（单进程内有效）
_cache: MetricSnapshot | None = None


def extract_metrics(raw_input: str, structured_metrics: dict[str, Any] | None = None) -> MetricSnapshot:
    """从文本和结构化数据中提取所有可量化指标。纯正则，不调 LLM。"""
    text = raw_input or ""

    numbers = re.findall(r"\d{1,4}(?:\.\d+)?%", text)  # 百分比
    numbers += re.findall(r"(?<!\d\.)\b\d{2,6}\b(?!\.\d)(?!%)", text)  # 整数

    amounts = re.findall(r"¥?\d{1,6}(?:\.\d+)?[万亿千百]?元?", text)
    amounts += re.findall(r"\$\d{1,6}(?:\.\d+)?[万亿千百]?", text)

    dates = re.findall(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?", text)
    dates += re.findall(r"(?:本周|上周|本月|上月|本季度|下月|下周)", text)

    entities = re.findall(r"(?:抖音|小红书|微博|公众号|微信|天猫|京东|淘宝|快手|B站|知乎)", text)
    platforms = [e for e in entities if e in ("抖音", "小红书", "微博", "公众号", "微信", "天猫", "京东", "淘宝", "快手", "B站", "知乎")]

    raw = structured_metrics or {}

    # 构建摘要
    parts: list[str] = []
    if numbers:
        parts.append(f"数字: {', '.join(numbers[:10])}")
    if amounts:
        parts.append(f"金额: {', '.join(amounts[:10])}")
    if dates:
        parts.append(f"日期: {', '.join(dates[:5])}")
    if entities:
        parts.append(f"渠道/实体: {', '.join(entities[:8])}")
    if raw:
        parts.append(f"结构化指标: {json.dumps(raw, ensure_ascii=False)[:500]}")

    snap = MetricSnapshot(
        numbers=numbers,
        amounts=amounts,
        dates=dates,
        entities=entities,
        platforms=platforms,
        raw_metrics=raw,
        summary="; ".join(parts) if parts else "无结构化指标",
    )
    global _cache
    _cache = snap
    return snap


def get_cached() -> MetricSnapshot | None:
    """获取最近一次提取的快照。"""
    return _cache


def inject_metrics_context(context: dict[str, Any]) -> dict[str, Any]:
    """将缓存的指标注入到 Agent 上下文中。"""
    snap = get_cached()
    if snap is None:
        return context
    enriched = dict(context)
    enriched["_metrics_summary"] = snap.summary
    enriched["_metrics_numbers"] = snap.numbers
    enriched["_metrics_amounts"] = snap.amounts
    enriched["_metrics_platforms"] = snap.platforms
    enriched["_structured_metrics"] = snap.raw_metrics
    return enriched


def clear_cache() -> None:
    global _cache
    _cache = None
