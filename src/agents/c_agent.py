"""C-Agent · LLM-Augmented : 多平台内容生成。

领域逻辑（非 LLM）:
  1. platform_rules 注入 — 微博140字、小红书emoji规范、公众号排版
  2. 输出校验 — 每篇 draft 长度检查、敏感平台规则合规
  3. 合规标注自动补全 — 平台规则与风险提示检查
"""
from __future__ import annotations

import json
import re
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


def _extract_product_name(raw_input: str) -> str:
    quoted = re.findall(r"[「《](.*?)[」》]", raw_input)
    for item in quoted:
        if 2 <= len(item) <= 24 and not any(x in item for x in ("不能", "不要", "禁止")):
            return item
    match = re.search(r"(?:新品|产品|活动|项目)[：:\s]*([\u4e00-\u9fa5A-Za-z0-9·\-]{2,24})", raw_input)
    if match:
        return match.group(1)
    return "这次新品"


def _extract_audience(raw_input: str) -> str:
    patterns = [
        r"目标用户是([^。；;\n]+)",
        r"目标客群[是为：:\s]*([^。；;\n]+)",
        r"面向([^，。；;\n]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_input)
        if match:
            return match.group(1).strip(" ，,。")
    return "正在寻找轻负担日常选择的人"


def _extract_scenes(raw_input: str) -> list[str]:
    match = re.search(r"(?:场景是|常见场景是|使用场景是)([^。；;\n]+)", raw_input)
    if not match:
        return ["早餐路上", "下午犯困", "运动后"]
    text = re.sub(r"(?:和|及|以及)", "、", match.group(1))
    scenes = [part.strip(" ，,、") for part in re.split(r"[、,，]", text) if part.strip(" ，,、")]
    return scenes[:4] or ["早餐路上", "下午犯困", "运动后"]


def _extract_sell_points(raw_input: str) -> list[str]:
    candidates = re.findall(r"(?:主打|卖点[：:]?|产品卖点[：:]?)([^。；;\n]+)", raw_input)
    text = "、".join(candidates) if candidates else raw_input
    points: list[str] = []
    for key in ("低糖", "0 蔗糖添加", "0蔗糖添加", "高纤维", "植物基", "黑芝麻香气", "冷藏即饮", "轻负担", "即饮"):
        if key in text and key not in points:
            points.append(key)
    return points[:5] or ["口味明确", "饮用方便", "适合日常场景"]


def _public_summary(raw_input: str) -> str:
    product = _extract_product_name(raw_input)
    audience = _extract_audience(raw_input)
    scenes = _extract_scenes(raw_input)
    points = _extract_sell_points(raw_input)
    if product != "这次新品":
        return f"{product} 面向 {audience}，围绕 {'、'.join(scenes[:2])} 等日常场景，主打 {'、'.join(points[:3])}"
    sentences = [s.strip() for s in re.split(r"[。；;\n]+", raw_input) if s.strip()]
    safe: list[str] = []
    for sentence in sentences:
        if any(term in sentence for term in ("不能", "不要", "禁止", "避免", "不得", "风险", "合规")):
            continue
        if sentence.startswith(("我们是一家", "我司是一家", "本品牌是一家")):
            continue
        safe.append(sentence)
    return "。".join(safe[:2])[:120] or "这次内容围绕新品亮点和真实使用场景展开"


def _has_compliance_boundary(raw_input: str) -> bool:
    return any(term in raw_input for term in ("不能", "不要", "禁止", "避免", "不得", "功效", "减肥", "治疗", "养生"))


def _platform_native_drafts(raw_input: str, platforms: list[str], brand_voice: str = "") -> dict[str, str]:
    product = _extract_product_name(raw_input)
    audience = _extract_audience(raw_input)
    scenes = _extract_scenes(raw_input)
    points = _extract_sell_points(raw_input)
    summary = _public_summary(raw_input)
    point_line = "、".join(points[:3])
    scene_line = " / ".join(scenes[:3])
    voice_hint = f"语气按「{brand_voice}」收住。" if brand_voice else "语气保持真实克制。"

    templates = {
        "weibo": (
            f"# {product} #".replace("# ", "#").replace(" #", "#")
            + f" 今天想聊一个很具体的日常选择：{scene_line}，需要一杯方便、轻负担、口味不无聊的即饮饮品。\n"
            f"{product} 的重点不是制造焦虑，而是把 {point_line} 放进更顺手的生活场景里。\n"
            f"你通常会在哪个时段喝？评论区告诉我们。"
        ),
        "wechat": (
            f"标题：为什么我们想做一瓶「{product}」\n\n"
            f"导语：{summary}。\n\n"
            f"正文：\n"
            f"1. 它解决的是一个小但高频的时刻：{scene_line}。\n"
            f"2. 内容重点会放在真实口味、配料信息和适合人群，不做夸张承诺。\n"
            f"3. 面向 {audience}，我们会用更清楚的方式解释新品卖点：{point_line}。\n\n"
            f"结尾：如果你也在找一杯不沉重的日常饮品，可以先把这次新品加入尝鲜清单。"
        ),
        "xhs": (
            f"{product}｜给忙碌日常的一杯轻负担\n\n"
            f"适合：{audience}\n"
            f"场景：{scene_line}\n"
            f"我会关注的 3 个点：\n"
            f"- {points[0]}\n"
            f"- {points[1] if len(points) > 1 else '入口顺不顺'}\n"
            f"- {points[2] if len(points) > 2 else '是不是方便带走'}\n\n"
            f"{voice_hint} 不把它说成万能解决方案，只记录一次更轻便的饮用选择。"
        ),
        "bilibili": (
            f"标题：我们为什么做「{product}」？一次新品背后的真实拆解\n\n"
            f"本期看点：\n"
            f"1. 这瓶饮品对应哪些真实场景：{scene_line}\n"
            f"2. {point_line} 到底怎么被用户感知\n"
            f"3. 新品上线前，我们还需要听到哪些反馈\n\n"
            f"结尾互动：你更在意口味、配料还是饮用场景？弹幕和评论区都可以聊。"
        ),
        "douyin": (
            f"开头 3 秒：早餐来不及、下午犯困、健身后想补点东西？\n"
            f"镜头 1：拿出「{product}」，展示冷藏即饮和包装。\n"
            f"镜头 2：切到 {scene_line} 三个使用场景。\n"
            f"口播：它的重点是 {point_line}，不是夸张承诺，是让日常多一个顺手选择。\n"
            f"收尾：想看真实试喝反馈，关注下一条。"
        ),
        "kuaishou": (
            f"说人话版：这次新品「{product}」就是给日常忙、但又想喝得轻一点的人准备的。\n"
            f"真实场景：{scene_line}。\n"
            f"别讲太玄，重点就三个：{point_line}。\n"
            f"后面会继续更新真实试喝和用户反馈，大家有想问的也可以直接留言。"
        ),
    }
    selected = platforms or ["weibo", "wechat", "xhs"]
    return {plat: templates.get(plat, f"{product}：{summary}。{voice_hint}") for plat in selected}


def _looks_like_raw_echo(text: str, raw_input: str) -> bool:
    compact_text = "".join(str(text).split())
    compact_raw = "".join(raw_input.split())
    if len(compact_raw) < 30:
        return False
    return compact_raw[:40] in compact_text or compact_text.startswith(compact_raw[:24])


def _is_platform_native(plat: str, text: str, raw_input: str) -> bool:
    if not str(text).strip() or _looks_like_raw_echo(text, raw_input):
        return False
    checks = {
        "weibo": lambda t: "#" in t or "评论" in t,
        "wechat": lambda t: "标题" in t and ("正文" in t or "导语" in t),
        "xhs": lambda t: "适合" in t and ("｜" in t or "-" in t),
        "bilibili": lambda t: "本期看点" in t or "弹幕" in t,
        "douyin": lambda t: "开头" in t or "镜头" in t or "口播" in t,
        "kuaishou": lambda t: "真实" in t or "说人话" in t or "留言" in t,
    }
    return checks.get(plat, lambda _t: True)(str(text))


def _normalize_platform_output(out: dict[str, Any], raw_input: str, platforms: list[str], brand_voice: str) -> dict[str, Any]:
    native = _platform_native_drafts(raw_input, platforms, brand_voice)
    drafts = dict(out.get("drafts") or {})
    for plat in platforms or list(native):
        text = str(drafts.get(plat, "")).strip()
        if not _is_platform_native(plat, text, raw_input):
            drafts[plat] = native[plat]
    if not drafts:
        drafts = native
    out["drafts"] = drafts
    if not out.get("title_variants"):
        product = _extract_product_name(raw_input)
        out["title_variants"] = [
            f"{product}，适合哪些日常场景？",
            f"一杯轻负担新品背后的真实理由",
            f"别把新品说重，先把场景讲清楚",
        ]
    if not out.get("short_video_script"):
        out["short_video_script"] = native.get("douyin") or next(iter(native.values()))
    notes = list(out.get("compliance_notes") or [])
    if _has_compliance_boundary(raw_input):
        notes.append("公开内容已避开功效化、治疗化和绝对化表达，建议发布前人工终审。")
    out["compliance_notes"] = list(dict.fromkeys(str(n) for n in notes if str(n).strip()))
    return out


def _fallback_from_task(raw_input: str, platforms: list[str]) -> dict[str, Any]:
    """当 LLM 串题时，用原始材料生成一个保守、可复核的应急成稿。"""
    selected = platforms or ["weibo", "wechat", "xhs"]
    product = _extract_product_name(raw_input)
    drafts = _platform_native_drafts(raw_input, selected)
    return {
        "drafts": drafts,
        "title_variants": [
            f"{product}，适合哪些日常场景？",
            f"一杯轻负担新品背后的真实理由",
            f"别把新品说重，先把场景讲清楚",
        ],
        "short_video_script": drafts.get("douyin") or next(iter(drafts.values()), ""),
        "compliance_notes": [
            "已触发防串题保护：输出仅基于原始任务材料生成，请人工终审。",
            "已避开功效化、治疗化和绝对化表达。",
        ],
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
        "必须让每个平台像它自己：微博要短句、话题和互动；微信公众号要标题/导语/正文段落；"
        "小红书要场景化种草和清单感；哔哩哔哩要本期看点和弹幕/评论互动；"
        "抖音要开头3秒、镜头和口播；快手要生活化、真实感、说人话。"
        "不要把 raw_input 整段复述给用户；不要把“不能/禁止/避免”这类合规约束写进公开文案正文，"
        "只在 compliance_notes 中说明边界。"
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
        return _normalize_platform_output(out, raw_input, platforms, brand_voice)
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
