"""Agent 输出渲染器 — 每种 Agent 输出按各自岗位的需求格式化展示。"""
from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

from src.display_labels import PLATFORM_LABELS, label_key, label_value


def _e(value: Any) -> str:
    return escape(str(value))


def _label_key(key: Any) -> str:
    return label_key(key)


def _label_value(value: Any) -> str:
    return label_value(value)


def _compact_text(value: Any, limit: int = 420) -> str:
    text = " ".join(_label_value(value).strip().split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _section_title(title: str, meta: str = "") -> None:
    meta_html = f"<span>{_e(meta)}</span>" if meta else ""
    st.markdown(
        f"<div class='oa-output-title'><strong>{_e(title)}</strong>{meta_html}</div>",
        unsafe_allow_html=True,
    )


def _text_card(text: Any, *, index: int | None = None, meta: str = "", kind: str = "plain", limit: int = 520) -> None:
    idx = f"<i>{index:02d}</i>" if index is not None else "<i>--</i>"
    meta_html = f"<em>{_e(meta)}</em>" if meta else ""
    st.markdown(
        f"<div class='oa-output-card oa-output-card--{kind}'>{idx}<span>{meta_html}{_e(_compact_text(text, limit))}</span></div>",
        unsafe_allow_html=True,
    )


def _dict_card(item: dict[str, Any], *, index: int | None = None, kind: str = "plain") -> None:
    idx = f"<i>{index:02d}</i>" if index is not None else "<i>--</i>"
    parts = "".join(
        f"<span><b>{_e(_label_key(k))}</b>{_e(_compact_text(v, 180))}</span>"
        for k, v in item.items()
        if not str(k).startswith("_")
    )
    st.markdown(
        f"<div class='oa-output-card oa-output-card--{kind}'>{idx}<div>{parts}</div></div>",
        unsafe_allow_html=True,
    )


def _chips(items: list[Any], *, prefix: str = "") -> None:
    html = "".join(f"<span>{_e(prefix)}{_e(item)}</span>" for item in items)
    st.markdown(f"<div class='oa-output-chips'>{html}</div>", unsafe_allow_html=True)


def _draft_preview(text: str) -> None:
    st.markdown(
        f"<div class='oa-draft-preview'>{_e(text)}</div>",
        unsafe_allow_html=True,
    )


def _draft_height(text: str) -> int:
    lines = str(text).count("\n") + max(1, len(str(text)) // 34)
    return max(240, min(520, 96 + lines * 24))


def render(agent_id: str, output: dict[str, Any], *, key_prefix: str = "") -> None:
    """根据 Agent 类型分发到对应的渲染器。"""
    renderer = _RENDERERS.get(agent_id.upper())
    if renderer:
        renderer(output, key_prefix=key_prefix or agent_id.upper())
    else:
        st.json(output)


# ── D-Agent: 数据运营 ──

def _render_d(output: dict[str, Any], *, key_prefix: str = "") -> None:
    # 洞察卡片
    insights = output.get("insights") or []
    if insights:
        _section_title("关键洞察")
        for i, ins in enumerate(insights, 1):
            st.markdown(
                f"<div class='oa-insight-card'><b>{i:02d}</b><span>{_e(ins)}</span></div>",
                unsafe_allow_html=True,
            )

    # 传播角度
    angles = output.get("angles") or []
    if angles:
        _section_title("传播角度")
        st.markdown("<div class='oa-output-grid'>", unsafe_allow_html=True)
        for idx, a in enumerate(angles, 1):
            _text_card(a, index=idx, kind="angle")
        st.markdown("</div>", unsafe_allow_html=True)

    # 风险标记
    risks = output.get("risk_flags") or []
    rule_risks = output.get("_rule_risks") or []
    all_risks = list(risks) + [r.get("description", str(r)) for r in rule_risks if isinstance(r, dict)]
    if all_risks:
        _section_title("风险标记")
        for idx, r in enumerate(all_risks, 1):
            _text_card(r, index=idx, kind="risk", limit=260)

    # 证据摘录
    evidence = output.get("evidence_spans") or []
    if evidence:
        _section_title("证据摘录", "从原始任务材料中抽取")
        for idx, ev in enumerate(evidence, 1):
            if isinstance(ev, dict):
                st.markdown(
                    "<div class='oa-evidence-card'>"
                    f"<b>{idx:02d}</b>"
                    f"<span>{_e(ev.get('field', 'raw_input'))}</span>"
                    f"<p>{_e(_compact_text(ev.get('snippet', ''), 260))}</p>"
                    "</div>",
                    unsafe_allow_html=True,
                )


# ── C-Agent: 内容运营 ──

def _render_c(output: dict[str, Any], *, key_prefix: str = "") -> None:
    drafts = output.get("drafts") or {}
    labels = PLATFORM_LABELS

    # 平台 Tab 切换
    if drafts:
        platforms = list(drafts.keys())
        tabs = st.tabs([labels.get(plat, plat) for plat in platforms])
        for idx, plat in enumerate(platforms):
            with tabs[idx]:
                _section_title(labels.get(plat, plat), f"{len(drafts[plat])} 字")
                _draft_preview(str(drafts[plat]))
                st.text_area(
                    "复制区",
                    value=drafts[plat],
                    height=_draft_height(str(drafts[plat])),
                    key=f"{key_prefix}_draft_{plat}",
                )
                _text_card("可直接复制使用，建议人工终审后发布。", kind="note", limit=80)

    # 标题变体
    titles = output.get("title_variants") or []
    if titles:
        _section_title("备选标题")
        for idx, t in enumerate(titles, 1):
            _text_card(t, index=idx, kind="title", limit=120)

    # 口播稿
    script = output.get("short_video_script") or ""
    if script.strip():
        _section_title("口播稿")
        _text_card(script, kind="script", limit=800)

    # 合规说明
    compliance = output.get("compliance_notes") or []
    if compliance:
        _section_title("合规说明")
        for idx, c in enumerate(compliance, 1):
            _text_card(c, index=idx, kind="note", limit=240)


# ── U-Agent: 用户运营 ──

def _render_u(output: dict[str, Any], *, key_prefix: str = "") -> None:
    segments = output.get("segments") or []
    if segments:
        _section_title("用户分群")
        for idx, seg in enumerate(segments, 1):
            if isinstance(seg, dict):
                _dict_card(seg, index=idx, kind="segment")

    # 生命周期
    lc = output.get("lifecycle_stage", "")
    if lc:
        stages = ["acquisition", "activation", "retention", "revenue", "referral"]
        labels = ["获取", "激活", "留存", "变现", "推荐"]
        idx = stages.index(lc) if lc in stages else 2
        stage_notes = {
            "获取": "关注新用户来源、首触达信息和进入路径，先让目标用户知道为什么要看。",
            "激活": "关注用户第一次完成关键动作，降低理解成本，并给出明确下一步。",
            "留存": "关注持续使用、复访和复购前的触达节奏，避免一次性热度流失。",
            "变现": "关注付费、转化、权益和价格表达，检查承诺边界与转化摩擦。",
            "推荐": "关注分享、口碑、社群扩散和老用户带新用户的动作设计。",
        }
        _section_title("生命周期阶段")
        selected_label = st.radio(
            "生命周期阶段",
            labels,
            index=idx,
            horizontal=True,
            key=f"{key_prefix}_lifecycle_stage_view",
            label_visibility="collapsed",
        )
        _dict_card(
            {
                "当前查看": selected_label,
                "Agent 判断": labels[idx],
                "运营含义": stage_notes.get(selected_label, ""),
            },
            kind="stage",
        )

    # 留存动作
    actions = output.get("retention_actions") or []
    if actions:
        _section_title("触达策略")
        for idx, a in enumerate(actions, 1):
            if isinstance(a, dict):
                _dict_card(a, index=idx, kind="action")

    # 流失风险
    churn = output.get("churn_risks") or []
    if churn:
        _section_title("流失风险")
        for idx, c in enumerate(churn, 1):
            _text_card(c, index=idx, kind="risk", limit=220)


# ── A-Agent: 活动运营 ──

def _render_a(output: dict[str, Any], *, key_prefix: str = "") -> None:
    plan = output.get("campaign_plan") or []
    if plan:
        _section_title("战役计划")
        for idx, phase in enumerate(plan, 1):
            if isinstance(phase, dict):
                _dict_card(phase, index=idx, kind="plan")

    # ROI
    roi = output.get("roi_estimate") or {}
    if isinstance(roi, dict) and roi.get("summary"):
        _section_title("ROI 预估")
        _text_card(roi.get("summary", ""), kind="metric", limit=360)
        conf = roi.get("confidence", "")
        if conf:
            _text_card(conf, meta="置信度", kind="note", limit=80)


# ── F-Agent: 流量运营 ──

def _render_f(output: dict[str, Any], *, key_prefix: str = "") -> None:
    scores = output.get("channel_scores") or []
    if scores:
        _section_title("渠道评分")
        for idx, s in enumerate(scores, 1):
            if isinstance(s, dict):
                _dict_card(s, index=idx, kind="score")

    # 预算
    budget = output.get("budget_allocation") or []
    if budget:
        _section_title("预算分配")
        for idx, b in enumerate(budget, 1):
            if isinstance(b, dict):
                pct = max(0, min(100, int(float(b.get("percent", 0) or 0))))
                st.markdown(
                    "<div class='oa-budget-row'>"
                    f"<i>{idx:02d}</i><span>{_e(_label_value(b.get('channel','')))}</span>"
                    f"<div><b style='width:{pct}%'></b></div><strong>{pct}%</strong>"
                    f"<small>{_e(_compact_text(b.get('rationale', ''), 120))}</small>"
                    "</div>",
                    unsafe_allow_html=True,
                )

    # 转化提示
    hints = output.get("conversion_hints") or []
    if hints:
        _section_title("转化优化")
        for idx, h in enumerate(hints, 1):
            _text_card(h, index=idx, kind="action", limit=240)


# ── N-Agent: 渠道运营 ──

def _render_n(output: dict[str, Any], *, key_prefix: str = "") -> None:
    sched = output.get("schedule_suggestions") or []
    if sched:
        _section_title("排期建议")
        for idx, s in enumerate(sched, 1):
            if isinstance(s, dict):
                _dict_card({
                    "平台": PLATFORM_LABELS.get(str(s.get("platform", "")), str(s.get("platform", ""))),
                    "时间窗": s.get("window", ""),
                    "理由": s.get("reason", ""),
                }, index=idx, kind="schedule")

    tags = output.get("hashtags") or []
    if tags:
        _section_title("推荐标签")
        _chips(tags, prefix="#")


# ── E-Agent: 交易运营 ──

def _render_e(output: dict[str, Any], *, key_prefix: str = "") -> None:
    funnel = output.get("funnel_steps") or []
    if funnel:
        _section_title("转化漏斗")
        for idx, f in enumerate(funnel, 1):
            if isinstance(f, dict):
                _dict_card(f, index=idx, kind="funnel")

    promos = output.get("promo_suggestions") or []
    if promos:
        _section_title("促销方案")
        for idx, p in enumerate(promos, 1):
            if isinstance(p, dict):
                _dict_card(p, index=idx, kind="action")

    ctas = output.get("cta_variants") or []
    if ctas:
        _section_title("CTA 变体")
        for idx, c in enumerate(ctas, 1):
            _text_card(c, index=idx, kind="title", limit=140)


# ── M/P/S: 策略建议型 ──

def _render_generic_cards(output: dict[str, Any], *, key_prefix: str = "") -> None:
    """通用渲染：按 key 展示为结构化卡片。"""
    for key, val in output.items():
        if key.startswith("_"):
            continue
        _section_title(_label_key(key))
        if isinstance(val, list):
            for idx, item in enumerate(val, 1):
                if isinstance(item, dict):
                    _dict_card(item, index=idx)
                else:
                    st.markdown(
                        f"<div class='oa-output-card'><i>{idx:02d}</i><span>{_e(_compact_text(item))}</span></div>",
                        unsafe_allow_html=True,
                    )
        elif isinstance(val, dict):
            for idx, (k, v) in enumerate(val.items(), 1):
                st.markdown(
                    f"<div class='oa-output-card'><i>{idx:02d}</i><span><b>{_e(_label_key(k))}</b>{_e(_compact_text(v))}</span></div>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                f"<div class='oa-output-card'><i>--</i><span>{_e(_compact_text(val))}</span></div>",
                unsafe_allow_html=True,
            )


# ── 渲染器注册表 ──

_RENDERERS: dict[str, Any] = {
    "D": _render_d,
    "C": _render_c,
    "U": _render_u,
    "A": _render_a,
    "F": _render_f,
    "N": _render_n,
    "E": _render_e,
    "M": _render_generic_cards,
    "P": _render_generic_cards,
    "S": _render_generic_cards,
}
