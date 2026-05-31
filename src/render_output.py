"""Agent 输出渲染器 — 每种 Agent 输出按各自岗位的需求格式化展示。"""
from __future__ import annotations

from typing import Any

import streamlit as st


def render(agent_id: str, output: dict[str, Any]) -> None:
    """根据 Agent 类型分发到对应的渲染器。"""
    renderer = _RENDERERS.get(agent_id.upper())
    if renderer:
        renderer(output)
    else:
        st.json(output)


# ── D-Agent: 数据运营 ──

def _render_d(output: dict[str, Any]) -> None:
    # 洞察卡片
    insights = output.get("insights") or []
    if insights:
        st.markdown("**关键洞察**")
        for i, ins in enumerate(insights, 1):
            st.markdown(
                f"<div style='padding:10px 14px;margin:6px 0;border-radius:8px;"
                f"background:rgba(0,200,184,0.06);border:1px solid rgba(0,200,184,0.15);"
                f"font-size:0.92rem;line-height:1.5;'>{i}. {ins}</div>",
                unsafe_allow_html=True,
            )

    # 传播角度
    angles = output.get("angles") or []
    if angles:
        st.markdown("**传播角度**")
        cols = st.columns(min(len(angles), 3))
        for idx, a in enumerate(angles):
            with cols[idx % 3]:
                st.info(a)

    # 风险标记
    risks = output.get("risk_flags") or []
    rule_risks = output.get("_rule_risks") or []
    all_risks = list(risks) + [r.get("description", str(r)) for r in rule_risks if isinstance(r, dict)]
    if all_risks:
        st.markdown("**风险标记**")
        for r in all_risks:
            st.warning(str(r)[:200])

    # 证据摘录
    evidence = output.get("evidence_spans") or []
    if evidence:
        st.markdown("**证据摘录**")
        for ev in evidence:
            if isinstance(ev, dict):
                st.code(f"[{ev.get('field', '')}] {ev.get('snippet', '')}", language=None)


# ── C-Agent: 内容运营 ──

def _render_c(output: dict[str, Any]) -> None:
    drafts = output.get("drafts") or {}

    # 平台 Tab 切换
    if drafts:
        platforms = list(drafts.keys())
        tabs = st.tabs(platforms)
        labels = {"weibo": "微博", "wechat": "公众号", "xhs": "小红书"}
        for idx, plat in enumerate(platforms):
            with tabs[idx]:
                st.caption(f"**{labels.get(plat, plat)}** · {len(drafts[plat])} 字")
                st.text_area(
                    f"{plat}_draft",
                    value=drafts[plat],
                    height=200,
                    key=f"draft_{plat}",
                    label_visibility="collapsed",
                )
                st.caption("可直接复制使用，建议人工终审后发布")

    # 标题变体
    titles = output.get("title_variants") or []
    if titles:
        st.markdown("**备选标题**")
        for t in titles:
            st.markdown(f"- {t}")

    # 口播稿
    script = output.get("short_video_script") or ""
    if script.strip():
        st.markdown("**口播稿**")
        st.info(script)

    # 合规说明
    compliance = output.get("compliance_notes") or []
    if compliance:
        for c in compliance:
            st.caption(f"✓ {c}")


# ── U-Agent: 用户运营 ──

def _render_u(output: dict[str, Any]) -> None:
    segments = output.get("segments") or []
    if segments:
        st.markdown("**用户分群**")
        cols = st.columns(min(len(segments), 3))
        for idx, seg in enumerate(segments):
            if isinstance(seg, dict):
                prio = seg.get("priority", "")
                color = {"high": "#f06565", "medium": "#e2a654", "low": "#8892a8"}.get(prio, "#8892a8")
                with cols[idx % 3]:
                    st.markdown(
                        f"<div style='padding:12px;border-radius:8px;background:rgba(255,255,255,0.02);"
                        f"border:1px solid {color};border-left:3px solid {color};'>"
                        f"<strong>{seg.get('name','')}</strong><br/>"
                        f"<small style='color:#8892a8;'>{seg.get('description','')}</small><br/>"
                        f"<span style='color:{color};font-size:0.72rem;font-weight:600;'>{prio.upper()}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

    # 生命周期
    lc = output.get("lifecycle_stage", "")
    if lc:
        stages = ["acquisition", "activation", "retention", "revenue", "referral"]
        labels = ["获取", "激活", "留存", "变现", "推荐"]
        idx = stages.index(lc) if lc in stages else 2
        st.markdown("**生命周期阶段**")
        cols = st.columns(5)
        for i, (s, l) in enumerate(zip(stages, labels)):
            with cols[i]:
                if i == idx:
                    st.markdown(f"**{l}** ←")
                else:
                    st.caption(l)

    # 留存动作
    actions = output.get("retention_actions") or []
    if actions:
        st.markdown("**触达策略**")
        for a in actions:
            if isinstance(a, dict):
                st.markdown(
                    f"- **{a.get('segment','')}** → {a.get('action','')} "
                    f"（{a.get('channel','')}）"
                )

    # 流失风险
    churn = output.get("churn_risks") or []
    if churn:
        for c in churn:
            st.warning(str(c)[:200])


# ── A-Agent: 活动运营 ──

def _render_a(output: dict[str, Any]) -> None:
    plan = output.get("campaign_plan") or []
    if plan:
        st.markdown("**战役计划**")
        for phase in plan:
            if isinstance(phase, dict):
                phase_name = phase.get("phase", "")
                obj = phase.get("objective", "")
                tasks = phase.get("tasks") or []
                with st.expander(f"{phase_name} · {obj}"):
                    for t in tasks:
                        st.markdown(f"- {t}")

    # ROI
    roi = output.get("roi_estimate") or {}
    if isinstance(roi, dict) and roi.get("summary"):
        st.markdown("**ROI 预估**")
        st.info(roi.get("summary", ""))
        conf = roi.get("confidence", "")
        if conf:
            color = {"high": "green", "medium": "orange", "low": "red"}.get(conf, "grey")
            st.caption(f"置信度：:{color}[{conf}]")


# ── F-Agent: 流量运营 ──

def _render_f(output: dict[str, Any]) -> None:
    scores = output.get("channel_scores") or []
    if scores:
        st.markdown("**渠道评分**")
        for s in scores:
            if isinstance(s, dict):
                sc = s.get("score", 0)
                color = "#3ecf8e" if sc >= 80 else ("#00c8b8" if sc >= 60 else ("#e2a654" if sc >= 40 else "#f06565"))
                st.markdown(
                    f"**{s.get('channel','')}** "
                    f"<span style='color:{color};font-weight:700;'>{sc}</span> · "
                    f"<small>{s.get('rationale','')}</small>",
                    unsafe_allow_html=True,
                )

    # 预算
    budget = output.get("budget_allocation") or []
    if budget:
        st.markdown("**预算分配**")
        for b in budget:
            if isinstance(b, dict):
                pct = b.get("percent", 0)
                st.markdown(
                    f"<div style='display:flex;align-items:center;gap:12px;padding:4px 0;'>"
                    f"<span style='width:80px;font-size:0.82rem;'>{b.get('channel','')}</span>"
                    f"<div style='flex:1;height:8px;border-radius:4px;background:rgba(255,255,255,0.06);'>"
                    f"<div style='width:{pct}%;height:100%;border-radius:4px;background:#00c8b8;'></div></div>"
                    f"<span style='font-family:monospace;font-size:0.82rem;width:40px;text-align:right;'>{pct}%</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # 转化提示
    hints = output.get("conversion_hints") or []
    if hints:
        st.markdown("**转化优化**")
        for h in hints:
            st.markdown(f"- {h}")


# ── N-Agent: 渠道运营 ──

def _render_n(output: dict[str, Any]) -> None:
    sched = output.get("schedule_suggestions") or []
    if sched:
        st.markdown("**排期建议**")
        rows = []
        for s in sched:
            if isinstance(s, dict):
                rows.append({
                    "平台": s.get("platform", ""),
                    "时间窗": s.get("window", ""),
                    "理由": s.get("reason", ""),
                })
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)

    tags = output.get("hashtags") or []
    if tags:
        st.markdown("**推荐标签**")
        tag_html = " ".join(
            f"<span style='display:inline-block;padding:4px 10px;margin:2px;border-radius:12px;"
            f"background:rgba(0,200,184,0.12);color:#00c8b8;font-size:0.78rem;font-family:monospace;'>#{t}</span>"
            for t in tags
        )
        st.markdown(tag_html, unsafe_allow_html=True)


# ── E-Agent: 交易运营 ──

def _render_e(output: dict[str, Any]) -> None:
    funnel = output.get("funnel_steps") or []
    if funnel:
        st.markdown("**转化漏斗**")
        for idx, f in enumerate(funnel):
            if isinstance(f, dict):
                ratio = 1.0 - idx * 0.22
                st.markdown(
                    f"<div style='display:flex;align-items:center;gap:12px;padding:6px 0;'>"
                    f"<span style='width:50px;font-size:0.78rem;font-weight:600;'>{f.get('step','')}</span>"
                    f"<div style='flex:1;height:22px;border-radius:4px;background:rgba(0,200,184,{ratio:.2f});display:flex;align-items:center;padding-left:10px;'>"
                    f"<span style='font-size:0.72rem;'>{f.get('description','')}</span></div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    promos = output.get("promo_suggestions") or []
    if promos:
        st.markdown("**促销方案**")
        for p in promos:
            if isinstance(p, dict):
                st.markdown(
                    f"<div style='padding:8px 12px;margin:4px 0;border-radius:8px;"
                    f"background:rgba(0,200,184,0.06);border:1px solid rgba(0,200,184,0.15);'>"
                    f"<strong>{p.get('offer','')}</strong><br/>"
                    f"<small style='color:#8892a8;'>约束：{p.get('constraint','')}</small>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    ctas = output.get("cta_variants") or []
    if ctas:
        st.markdown("**CTA 变体**")
        for c in ctas:
            st.markdown(f"- `{c}`")


# ── M/P/S: 策略建议型 ──

def _render_generic_cards(output: dict[str, Any]) -> None:
    """通用渲染：按 key 展示为结构化卡片。"""
    for key, val in output.items():
        if key.startswith("_"):
            continue
        st.markdown(f"**{key}**")
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    parts = [f"**{k}**: {v}" for k, v in item.items()]
                    st.markdown(" · ".join(parts))
                else:
                    st.markdown(f"- {item}")
        elif isinstance(val, dict):
            for k, v in val.items():
                st.caption(f"{k}: {v}")
        else:
            st.caption(str(val)[:300])


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
