"""M-Agent · 市场运营：品牌定位、竞品分析、渠道组合（LLM + Mock 双路径）。"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..llm_json import chat_json_parse

MOCK: dict[str, Any] = {
    "positioning": "学生主办、本地乐队、安全包容的校园户外音乐节——差异化在「无酒精友好 + 学生自治叙事」",
    "competitive_notes": [
        {"topic": "同类校园活动", "note": "多由学生会或团委主导，宣传口径偏官方；本活动强调「学生主办」的野生气质"},
        {"topic": "商业音乐节", "note": "避免对标票价与阵容规模；强调参与感、地缘认同与安全体验"},
        {"topic": "本地 Livehouse", "note": "有稳定受众但容量有限；户外校园场景可承接溢出人群，互补大于竞争"},
    ],
    "channel_mix": [
        {"channel": "weibo", "role": "扩散与话题发酵", "weight": "高"},
        {"channel": "wechat", "role": "深度叙事与转化", "weight": "中"},
        {"channel": "xhs", "role": "图文种草与社群氛围", "weight": "高"},
        {"channel": "douyin", "role": "彩排花絮短视频触达泛校园人群", "weight": "中"},
    ],
}


def validate(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not payload.get("positioning"):
        issues.append("缺少品牌定位")
    if not payload.get("channel_mix"):
        issues.append("缺少渠道组合建议")
    cms = payload.get("channel_mix") or []
    if len(cms) < 3:
        issues.append("渠道组合应至少覆盖 3 个渠道")
    return issues


def _m_fallback(raw_input: str) -> dict[str, Any]:
    snippet = raw_input.strip().replace("\n", " ")[:160]
    return {
        "positioning": f"模型降级，请人工评估。素材摘要：{snippet}",
        "competitive_notes": [{"topic": "请人工分析", "note": "LLM 不可用"}],
        "channel_mix": [{"channel": "综合", "role": "待评估", "weight": "待定"}],
        "_operai_fallback": "M-Agent LLM 不可用，已降级",
    }


def run_m(
    *, use_llm: bool, context: dict[str, Any],
    llm_cfg: dict[str, Any], root: Path | None = None,
) -> dict[str, Any]:
    _ = root
    if not use_llm:
        return deepcopy(MOCK)

    raw_input = str(context.get("raw_input", ""))
    upstream = context.get("upstream") or {}
    d_out = upstream.get("D") or {}

    system = (
        "你是市场运营分析专家。根据素材和洞察，输出品牌定位和渠道策略。"
        "只输出合法 JSON：positioning(一句话定位)、competitive_notes(对象数组, 每项 topic+note)、"
        "channel_mix(对象数组, 每项 channel+role+weight)。"
        "风格专业克制，避免空泛表述。"
    )
    payload: dict[str, Any] = {"raw_input": raw_input}
    if d_out:
        payload["d_insights"] = d_out.get("insights") or []
        payload["d_angles"] = d_out.get("angles") or []
    user = json.dumps(payload, ensure_ascii=False)

    try:
        return chat_json_parse(
            system=system, user=user, llm_cfg=llm_cfg,
            max_tokens=min(int(llm_cfg.get("max_tokens", 2048)), 1200),
        )
    except Exception:
        return _m_fallback(raw_input)


run_m_plugin = run_m
