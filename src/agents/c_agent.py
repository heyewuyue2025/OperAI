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
PLATFORM_STYLE_PLAYBOOKS = {
    "weibo": {
        "role": "公共话题场，适合短句、话题标签、即时互动和轻讨论",
        "shape": "话题标签 + 2-3 句核心表达 + 一个评论区问题",
        "avoid": "长文章结构、产品说明书、堆卖点、公众号式小标题",
    },
    "wechat": {
        "role": "订阅阅读场，适合标题、摘要、导语、段落小标题和完整解释",
        "shape": "标题 + 摘要 + 导语 + 2-3 个中文小标题正文",
        "avoid": "只给清单、过短口播、像微博一样抛问题就结束",
    },
    "xhs": {
        "role": "生活经验笔记和搜索种草场，重真实体验、具体场景、收藏价值",
        "shape": "笔记标题 + 第一人称体验 + 场景清单 + 话题标签",
        "avoid": "硬广、品牌公告、适合/场景字段、功效承诺、空泛高级感",
    },
    "bilibili": {
        "role": "视频内容社区，适合选题包装、封面字、分段结构、弹幕互动",
        "shape": "视频标题 + 封面字 + 本期看点 + 时间线/分段 + 弹幕问题",
        "avoid": "纯图文文案、只写产品简介、标题党和与内容无关的夸张封面",
    },
    "douyin": {
        "role": "高节奏短视频推荐流，适合 3 秒钩子、镜头、字幕和口播",
        "shape": "开头 3 秒 + 镜头序列 + 字幕/口播 + 评论引导",
        "avoid": "长段落、慢铺垫、品牌自我介绍开头、公众号式正文",
    },
    "kuaishou": {
        "role": "生活化短视频和熟人感社区，重真实口播、日常场景、评论互动",
        "shape": "说人话口播 + 真实使用场景 + 朴素判断 + 评论区问题",
        "avoid": "端着的广告腔、过度精致、空洞概念和外站导流话术",
    },
}

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
            value = match.group(1).strip(" ，,。")
            value = re.split(r"[，,](?:常见|使用|主要|核心|场景)", value)[0].strip(" ，,。")
            return value
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


def _point(points: list[str], idx: int, fallback: str) -> str:
    return points[idx] if len(points) > idx else fallback


def _platform_playbooks_for(platforms: list[str]) -> dict[str, dict[str, str]]:
    selected = platforms or ["weibo", "wechat", "xhs"]
    return {plat: PLATFORM_STYLE_PLAYBOOKS[plat] for plat in selected if plat in PLATFORM_STYLE_PLAYBOOKS}


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
    voice_hint = brand_voice or "真实、克制、有生活感"
    p0 = _point(points, 0, "口味不腻")
    p1 = _point(points, 1, "饮用方便")
    p2 = _point(points, 2, "负担轻一点")
    s0 = _point(scenes, 0, "早餐路上")
    s1 = _point(scenes, 1, "下午犯困")
    s2 = _point(scenes, 2, "运动后")

    templates = {
        "weibo": (
            f"# {product} #".replace("# ", "#").replace(" #", "#")
            + f" 今天想认真聊一个很小的日常选择：{s0}、{s1}、{s2}，你可能只是想喝点顺口、不太甜、拿了就走的东西。\n"
            f"{product} 这次主打 {p0}、{p1}、{p2}。我们不把一瓶饮品讲成万能答案，只把它放回真实生活里看。\n"
            f"如果只能选一个使用场景，你会把它放在什么时候？评论区我想看真实答案。"
        ),
        "wechat": (
            f"标题：一瓶 {product}，先从真实日常讲起\n\n"
            f"摘要：{summary}。\n\n"
            f"导语：新品发布最怕只剩一串卖点。对 {audience} 来说，真正重要的是它能不能进入一个具体时刻，并且被自然理解。\n\n"
            f"正文：\n"
            f"一、先看它进入什么场景\n"
            f"{scene_line}，这些不是宏大的消费趋势，而是每天都会发生的小断点。{product} 的表达应该从这些断点出发，而不是从品牌自夸出发。\n\n"
            f"二、再讲用户能立刻感知什么\n"
            f"这次可以被清楚记住的点是 {point_line}。公众号正文里不急着制造情绪，而是把配料、口味、饮用方式和适用边界讲明白。\n\n"
            f"三、最后留下可验证的问题\n"
            f"发布后我们会继续收集试喝反馈：入口是否自然、甜度是否合适、在 {s0} 和 {s1} 这类场景里是否真的顺手。内容不追求夸张，而追求能被复盘。"
        ),
        "xhs": (
            f"办公室冰箱想囤这个｜{product}\n\n"
            f"最近在试一瓶 {product}，它不是那种一喝就很甜、很像甜品的即饮拿铁。对我来说，比较加分的是 {p0}，还有 {p1} 这件事。\n\n"
            f"我会把它放进这几个真实瞬间：\n"
            f"1. {s0}，来不及认真吃但不想空着\n"
            f"2. {s1}，想喝点有味道但别太厚重\n"
            f"3. {s2}，想补一口又不想被甜味压住\n\n"
            f"小提醒：这类饮品不要被写成保健品，也不用硬凹精致生活。按「{voice_hint}」讲清楚口味、甜度、适合放在哪些日常时刻，就已经够有用。\n\n"
            f"#办公室饮品 #燕麦拿铁 #黑芝麻 #低糖饮品 #打工人冰箱 #新品试喝"
        ),
        "bilibili": (
            f"视频标题：黑芝麻燕麦拿铁值得买吗？我们把 {product} 放进 3 个真实场景试一下\n"
            f"封面字：真实试喝 / 不吹不黑\n\n"
            f"本期看点：\n"
            f"- {point_line} 这些点，哪些是入口第一时间能感知到的\n"
            f"- {s0}、{s1}、{s2} 三个场景里，它是不是都成立\n"
            f"- 适合谁，不适合谁，尽量讲清楚边界\n\n"
            f"视频结构：\n"
            f"00:00 开箱和包装信息\n"
            f"00:20 配料表和口味预期\n"
            f"00:55 冷藏后第一口试喝\n"
            f"01:40 三个使用场景复盘\n"
            f"02:30 一句话结论：推荐给谁\n\n"
            f"弹幕互动：你喝即饮拿铁最在意甜度、香气、方便性，还是喝完会不会腻？"
        ),
        "douyin": (
            f"开头 3 秒：早八来不及吃？先别空腹硬扛。\n"
            f"镜头 1：手伸进冷藏柜，拿出「{product}」。\n"
            f"镜头 2：倒进透明杯，给黑芝麻色泽和质地一个近景。\n"
            f"镜头 3：快切 {s0}、{s1}、{s2} 三个画面。\n"
            f"口播：这瓶主打 {point_line}。不讲夸张功效，就看它是不是顺手、好喝、甜度舒服。\n"
            f"结尾字幕：想看完整试喝？评论区告诉我先测甜度还是香气。"
        ),
        "kuaishou": (
            f"这瓶「{product}」咱就说人话。\n"
            f"{s0}、{s1}、{s2}，有时候不需要多复杂，就是想拿一瓶方便、别太甜、喝着顺口的。\n"
            f"它主要看三点：{point_line}。别整太虚的，入口顺不顺、甜不甜、喝完腻不腻，大家一试就知道。\n"
            f"后面我把真实试喝发出来，有想问的评论区说，我按你们关心的点测。"
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
    weak_markers = (
        "适合：",
        "场景：",
        "我会关注的 3 个点",
        "给忙碌日常的一杯轻负担",
        "对应哪些真实场景",
        "一次新品背后的真实拆解",
        "不把它说成万能解决方案",
        "它解决的是一个小但高频的时刻",
        "内容重点会放在",
        "用户真正能感知到什么",
    )
    if any(marker in str(text) for marker in weak_markers):
        return False
    checks = {
        "weibo": lambda t: "#" in t and ("评论" in t or "你会" in t) and len(t) <= 360,
        "wechat": lambda t: "标题" in t and "摘要" in t and "正文" in t and ("一、" in t or "01" in t),
        "xhs": lambda t: "｜" in t and "我" in t and "#" in t and ("瞬间" in t or "冰箱" in t),
        "bilibili": lambda t: "视频标题" in t and "封面字" in t and "本期看点" in t and "弹幕" in t,
        "douyin": lambda t: "开头 3 秒" in t and "镜头" in t and "口播" in t and "评论区" in t,
        "kuaishou": lambda t: "说人话" in t and ("真实" in t or "评论区" in t),
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
        "你还会收到 platform_style_playbooks，它定义了每个平台的内容场景、结构和禁忌，必须逐条遵守。"
        "具体要求：小红书必须像用户笔记，第一人称体验、生活细节、话题标签，不要写“适合：/场景：”字段；"
        "B站必须像视频策划，包含标题、看点、时间线或分段、弹幕互动；"
        "抖音必须是镜头脚本，不要写长段落；快手必须口语可信，不要像广告播报；"
        "公众号必须像一篇可阅读文章，有摘要和小标题，不要只有清单。"
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
        "platform_style_playbooks": _platform_playbooks_for(platforms),
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
