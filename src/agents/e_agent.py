"""E-Agent · 交易运营：转化漏斗、促销方案、CTA 优化（LLM + Mock 双路径）。"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..llm_json import chat_json_parse

MOCK: dict[str, Any] = {
    "funnel_steps": [
        {"step": "曝光", "description": "三平台内容触达在校用户与校友圈", "dropoff_risk": "信息流噪音，首屏吸引力不足"},
        {"step": "兴趣", "description": "点击/收藏/蹲后续，进入意向池", "dropoff_risk": "CTA 不明确导致流失"},
        {"step": "互动", "description": "评论/转发/填写预报名表单", "dropoff_risk": "表单过长或权限申请劝退"},
        {"step": "到场", "description": "线下参与或志愿者到场签到", "dropoff_risk": "交通指引不清、天气不确定"},
        {"step": "复购/传播", "description": "活动后 UGC 分享与下次活动预约", "dropoff_risk": "缺乏持续触达机制"},
    ],
    "promo_suggestions": [
        {"offer": "志愿者专属纪念周边", "constraint": "不承诺稀缺或升值，限定现场领取"},
        {"offer": "早鸟关注礼包（电子纪念票根 + 节目单预览）", "constraint": "明确领取截止时间，避免催促感"},
        {"offer": "三人同行预约通道", "constraint": "不强制分享朋友圈，尊重用户隐私选择"},
    ],
    "cta_variants": [
        "关注官方账号获取场次通知与彩排花絮",
        "评论区置顶查看 FAQ，报名入口见公众号菜单",
        "转发给想一起去的朋友，蹲后续场次更新",
        "志愿者报名通道已开启，不限年级与专业",
    ],
}


def validate(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    funnel = payload.get("funnel_steps") or []
    if len(funnel) < 3:
        issues.append("转化漏斗应至少包含 3 个阶段")
    promos = payload.get("promo_suggestions") or []
    for p in promos:
        if isinstance(p, dict) and not p.get("constraint"):
            issues.append(f"促销方案「{p.get('offer','')}」缺少约束条件")
    if not payload.get("cta_variants"):
        issues.append("缺少 CTA 变体")
    return issues


def _e_fallback(raw_input: str) -> dict[str, Any]:
    snippet = raw_input.strip().replace("\n", " ")[:160]
    return {
        "funnel_steps": [
            {"step": "曝光", "description": "内容触达", "dropoff_risk": "模型降级"},
            {"step": "转化", "description": "下单/参与", "dropoff_risk": "请人工补充"},
        ],
        "promo_suggestions": [{"offer": "请人工设计促销方案", "constraint": f"素材摘要：{snippet}"}],
        "cta_variants": ["请人工设计 CTA"],
        "_operai_fallback": "E-Agent LLM 不可用，已降级",
    }


def run_e(
    *, use_llm: bool, context: dict[str, Any],
    llm_cfg: dict[str, Any], root: Path | None = None,
) -> dict[str, Any]:
    _ = root
    if not use_llm:
        return deepcopy(MOCK)

    raw_input = str(context.get("raw_input", ""))
    upstream = context.get("upstream") or {}
    d_out = upstream.get("D") or {}
    c_out = upstream.get("C") or {}
    f_out = upstream.get("F") or {}

    system = (
        "你是电商/交易运营分析专家。根据素材和洞察，输出转化漏斗和促销方案。"
        "只输出合法 JSON：funnel_steps(对象数组, 每项 step+description+dropoff_risk)、"
        "promo_suggestions(对象数组, 每项 offer+constraint)、"
        "cta_variants(字符串数组, 不同场景的 CTA 文案)。"
        "促销约束必须明确——不得使用虚假紧迫感、不得承诺收益。"
    )
    payload: dict[str, Any] = {"raw_input": raw_input}
    if d_out:
        payload["d_insights"] = d_out.get("insights") or []
        payload["d_risk_flags"] = d_out.get("risk_flags") or []
    if c_out:
        payload["c_drafts_summary"] = {k: v[:200] for k, v in (c_out.get("drafts") or {}).items()}
    if f_out:
        payload["f_channel_scores"] = f_out.get("channel_scores") or []
    user = json.dumps(payload, ensure_ascii=False)

    try:
        return chat_json_parse(
            system=system, user=user, llm_cfg=llm_cfg,
            max_tokens=min(int(llm_cfg.get("max_tokens", 2048)), 1500),
        )
    except Exception:
        return _e_fallback(raw_input)


run_e_plugin = run_e
