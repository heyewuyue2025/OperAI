"""D-Agent · Rule-First : 数据洞察与证据溯源。

领域逻辑（非 LLM）:
  1. evidence_spans 必须从 raw_input 中可验证摘录 — 防止 LLM 编造证据
  2. risk_flags 模板匹配 — 金融/媒体场景的已知风险模式
  3. 数字/百分比提取 — 结构化 metrics 供下游 Agent 消费
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..llm_json import chat_json_parse

MOCK: dict[str, Any] = {
    "insights": [
        "活动具备「学生主办 + 本地乐队」双叙事，易形成参与感与地缘认同。",
        "安全与包容为校园场景硬约束，内容需显性提及而非口号化。",
    ],
    "angles": [
        "以「第一次户外彩排花絮」制造真实感与倒计时。",
        "以「志愿者/工作组」幕后视角强化可信与秩序。",
        "以「无酒精友好现场」回应校园活动常见舆情点。",
    ],
    "risk_flags": ["避免饮酒与过度营销承诺", "乐队版权与肖像需线下确认"],
    "evidence_spans": [
        {"field": "raw_input", "snippet": "户外音乐节"},
        {"field": "raw_input", "snippet": "安全、包容、学生主办"},
    ],
}


def validate(payload: dict[str, Any], *, raw_input: str = "") -> list[str]:
    """验证 D-Agent 输出质量。"""
    issues: list[str] = []
    if not payload.get("insights"):
        issues.append("缺少 insights")
    if not payload.get("risk_flags"):
        issues.append("risk_flags 为空，建议至少标注一条风险")
    for span in payload.get("evidence_spans") or []:
        snippet = str(span.get("snippet", ""))
        if snippet and raw_input and snippet not in raw_input:
            issues.append(f"证据摘录「{snippet[:40]}…」在原文中未找到，可能为 LLM 编造")
    return issues


def _extract_metrics(text: str) -> dict[str, list[str]]:
    """非 LLM：从原文提取结构化指标。"""
    numbers = re.findall(r"\d{1,4}(?:\.\d+)?%?", text)
    numbers += re.findall(r"(?<!\d\.)\b\d{2,6}\b(?!\.\d)(?!%)", text)
    amounts = re.findall(r"¥?\d{1,6}(?:\.\d+)?[万亿千百]?元?", text)
    amounts += re.findall(r"\$\d{1,6}(?:\.\d+)?[万亿千百]?", text)
    dates = re.findall(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?", text)
    dates += re.findall(r"(?:本周|上周|本月|上月|本季度|下月|下周)", text)
    entities = re.findall(r"(?:抖音|小红书|微博|公众号|微信|天猫|京东|淘宝|快手|B站|知乎|douyin|xiaohongshu|weibo|wechat|taobao|jd|kuaishou|tiktok)", text, re.IGNORECASE)
    return {"numbers": numbers, "amounts": amounts, "dates": dates, "entities": entities}


# 风险扫描规则库（行业通用 + Pack 扩展）
_RISK_PATTERNS: list[tuple[str, str, str]] = [
    # (风险类别, 正则, 说明)
    ("promise_return", r"承诺收益|保证收益|保证本金|稳赚|必赚|只赚不赔|躺赚|暴富|刚性兑付|包赚|guaranteed return|risk.free|no.risk", "承诺收益/保本嫌疑"),
    ("hype_claim", r"全网第一|史上最强|绝对保证|100%有效|必火|[Ff]irst.in.the.world|guaranteed.100", "夸大/绝对化表述"),
    ("unverified_info", r"据内部消息|据知情人士|网传[^，]{0,20}(?:属实|确认)|insider.says|unverified", "未核实信息"),
    ("personal_data", r"身份证号|\d{17}[\dXx]|手机号|银行卡号", "疑似个人敏感信息"),
    ("alcohol_minor", r"未成年人.*酒|酒.*未成年人|未成年.*饮", "未成年人+酒精风险"),
]


def scan_risks(text: str) -> list[dict[str, str]]:
    """非 LLM：基于规则库扫描风险信号。返回 found_risks 列表。"""
    found: list[dict[str, str]] = []
    seen_categories: set[str] = set()
    for category, pattern, desc in _RISK_PATTERNS:
        if category in seen_categories:
            continue
        if re.search(pattern, text):
            found.append({"category": category, "pattern": pattern, "description": desc, "source": "rule_engine"})
            seen_categories.add(category)
    return found


def _d_fallback(raw_input: str) -> dict[str, Any]:
    snippet = raw_input.strip().replace("\n", " ")[:160]
    return {
        "insights": ["（模型降级）以下为基于素材的应急要点，请人工复核。"],
        "angles": ["用可验证细节建立信任", "用「幕后/筹备」视角降低宣传感"],
        "risk_flags": ["请人工核对事实、合规与敏感表述"],
        "evidence_spans": [{"field": "raw_input", "snippet": snippet[:80]}],
        "_operai_fallback": "LLM 不可用，已降级",
    }


def run_d(*, use_llm: bool, raw_input: str, brand_voice: str, llm_cfg: dict[str, Any]) -> dict[str, Any]:
    metrics = _extract_metrics(raw_input)
    rule_risks = scan_risks(raw_input)

    if not use_llm:
        out = deepcopy(MOCK)
        out["_metrics"] = metrics
        out["_rule_risks"] = rule_risks
        return out

    system = (
        "你是数据与舆情方向的运营分析助手。只输出合法 JSON："
        "insights(字符串数组,1-8条), angles(字符串数组,1-5条), "
        "risk_flags(字符串数组), evidence_spans(对象数组，"
        "每项含 field 和 snippet，snippet 必须从用户原文中逐字摘录)。"
        "不要编造用户未提供的事实。"
    )
    user = json.dumps({"raw_input": raw_input, "brand_voice": brand_voice}, ensure_ascii=False)

    try:
        out = chat_json_parse(
            system=system, user=user, llm_cfg=llm_cfg,
            max_tokens=min(int(llm_cfg.get("max_tokens", 2048)), 1200),
        )
        out["_metrics"] = metrics
        out["_rule_risks"] = rule_risks
        return out
    except Exception:
        return _d_fallback(raw_input)


def run_d_plugin(*, use_llm: bool, context: dict[str, Any], llm_cfg: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    _ = root
    return run_d(
        use_llm=use_llm,
        raw_input=context.get("raw_input", ""),
        brand_voice=context.get("brand_voice", ""),
        llm_cfg=llm_cfg,
    )
