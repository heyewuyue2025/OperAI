"""C-Agent · LLM-Augmented : 多平台内容生成。

领域逻辑（非 LLM）:
  1. platform_rules 注入 — 微博140字、小红书emoji规范、公众号排版
  2. 输出校验 — 每篇 draft 长度检查、敏感平台规则合规
  3. 合规标注自动补全 — 金融 Pack 时检查风险提示
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..llm_json import chat_json_parse
from ..platform_rules import rules_for_platforms

# 平台硬限制（非 LLM 校验用）
PLATFORM_LIMITS = {"weibo": 2000, "wechat": 20000, "xhs": 1000}

MOCK: dict[str, Any] = {
    "drafts": {
        "weibo": "【校园音乐节】下月见。学生主办、现场友好、秩序在线。#校园生活#",
        "wechat": "我们准备了一场属于学生的户外音乐节：本地乐队与社团同台。",
        "xhs": "下月！学校草坪音乐节 学生主办|本地乐队|社团串场",
    },
    "title_variants": ["草坪上的第一次合排", "学生主办音乐节倒计时", "无酒精友好现场"],
    "short_video_script": "下个月，我们的校园音乐节要来了。关注官方账号。",
    "compliance_notes": [],
}


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
    if pack_id == "finance":
        all_text = " ".join(str(v) for v in drafts.values())
        if "风险" not in all_text and "投资需谨慎" not in all_text:
            issues.append("金融 Pack：文案缺少风险提示")
        if "承诺收益" in all_text or "保本" in all_text.replace("不保本", ""):
            issues.append("金融 Pack：文案疑似含承诺收益表述")
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


def run_c(
    *, use_llm: bool, d_out: dict[str, Any], platforms: list[str],
    llm_cfg: dict[str, Any], root: Path | None = None,
) -> dict[str, Any]:
    if not use_llm:
        return deepcopy(MOCK)

    system = (
        "你是内容运营。根据 insights 与 angles 写多平台文案。只输出 JSON："
        "drafts(键为平台代码，值为文案), title_variants(字符串数组3条), "
        "short_video_script(30-60秒口播稿), compliance_notes(合规说明数组)。"
        "风格克制可信，遵守 risk_flags。"
    )
    payload: dict[str, Any] = {"d_agent": d_out, "platforms": platforms}
    if root is not None:
        payload["platform_rules"] = rules_for_platforms(root, platforms)
    user = json.dumps(payload, ensure_ascii=False)

    try:
        return chat_json_parse(
            system=system, user=user, llm_cfg=llm_cfg,
            max_tokens=min(int(llm_cfg.get("max_tokens", 2048)), 2000),
        )
    except Exception:
        out = deepcopy(MOCK)
        out["_operai_fallback"] = "LLM 不可用，已降级为内置演示文案"
        return out


def run_c_plugin(*, use_llm: bool, context: dict[str, Any], llm_cfg: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    upstream = context.get("upstream") or {}
    d_out = upstream.get("D") or {}
    platforms = context.get("platforms") or ["weibo", "wechat", "xhs"]
    return run_c(use_llm=use_llm, d_out=d_out, platforms=platforms, llm_cfg=llm_cfg, root=root)
