"""OperAI 工作台 — 岗位 Agent 工作台。

每个运营岗位的人打开这个页面，选择自己的 Agent，
输入素材，运行，看到产出，验证质量，导出方案。
"""
from __future__ import annotations

import time
import uuid

import streamlit as st

from src.export_campaign import build_campaign_markdown
from src.data_hub import extract_metrics, get_cached
from src.harness.plugin_registry import list_plugins, invoke
from src.harness.verify_gate import evaluate as verify_evaluate, VerifyResult
from src.llm_runtime import effective_use_llm
from src.orchestrator import load_config, open_connection, llm_settings
from src.render_output import render as render_output
from src.storage.db import query_all, execute
from src.logutil import append_event
from pathlib import Path
import json
from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).resolve().parent
cfg = load_config(ROOT)
conn = open_connection(ROOT, cfg)

st.set_page_config(page_title="OperAI · 工作台", layout="wide")

# 注入设计令牌
_theme_path = ROOT / "frontend" / "streamlit-theme.css"
if _theme_path.is_file():
    st.markdown(f"<style>{_theme_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

# ── Agent 元数据 ──
AGENT_META = {
    "D": {"name": "数据运营", "desc": "全域数据聚合 · 指标提取 · 洞察生成 · 风险预警", "tier": "数据基座"},
    "U": {"name": "用户运营", "desc": "RFM 分群 · 生命周期判定 · 流失预警 · 触达策略", "tier": "LLM Augmented"},
    "C": {"name": "内容运营", "desc": "多平台文案 · 标题变体 · 口播脚本 · 合规检查", "tier": "LLM Augmented"},
    "A": {"name": "活动运营", "desc": "战役结构 · 预算建议 · ROI 预估 · 任务拆解", "tier": "LLM Augmented"},
    "N": {"name": "渠道运营", "desc": "智能排期 · 标签策略 · 平台适配 · 冲突检测", "tier": "Rule-First"},
    "F": {"name": "流量运营", "desc": "渠道评分 · 预算分配 · CAC 优化 · 转化分析", "tier": "LLM Augmented"},
    "M": {"name": "市场运营", "desc": "品牌定位 · 竞品分析 · 渠道组合 · 趋势洞察", "tier": "LLM Augmented"},
    "P": {"name": "产品运营", "desc": "功能分析 · UX 反馈归类 · 迭代优先级 · 数据归因", "tier": "LLM Augmented"},
    "S": {"name": "社群运营", "desc": "互动话术 · KOL 匹配 · 社群活动 · 情绪监测", "tier": "LLM Augmented"},
    "E": {"name": "交易运营", "desc": "转化漏斗 · 促销设计 · CTA 优化 · GMV 分析", "tier": "LLM Augmented"},
}

TIER_LABELS = {
    "数据基座": "统一数据层，所有 Agent 共享",
    "Rule-First": "领域规则引擎 + LLM 增强",
    "LLM Augmented": "LLM 推理 + 领域校验",
}

# ── Session ──
st.session_state.setdefault("task_id", str(uuid.uuid4()))
st.session_state.setdefault("last_result", None)
st.session_state.setdefault("selected_agent", "D")

# ── Sidebar: Agent 选择器 ──
with st.sidebar:
    st.markdown("## OperAI")
    st.caption("企业运营智能体平台")

    st.divider()

    # Agent 选择
    agent_ids = list(AGENT_META.keys())
    current_agent = st.session_state.get("selected_agent", "D")
    current_idx = agent_ids.index(current_agent) if current_agent in agent_ids else 0

    selected = st.selectbox(
        "选择你的岗位 Agent",
        options=agent_ids,
        format_func=lambda x: f"{x} · {AGENT_META[x]['name']}",
        index=current_idx,
    )

    if selected != current_agent:
        st.session_state["selected_agent"] = selected
        st.session_state["last_result"] = None
        st.rerun()

    meta = AGENT_META[selected]
    st.caption(f"**{meta['name']}** · {meta['tier']}")
    st.caption(meta["desc"])

    st.divider()

    # Harness 信息
    st.caption("**Harness 保障**")
    st.caption("· 每次运行自动提取结构化指标")
    st.caption("· 输出经过 validate() 规则校验")
    st.caption("· 全链路可观测（SQLite + JSONL）")
    st.caption("· 导出前经 Verify Gate 合规审查")

    st.divider()
    st.caption(f"task `{st.session_state['task_id'][:8]}…`")

# ── Main ──
aid = st.session_state["selected_agent"]
meta = AGENT_META[aid]

st.markdown(f"### {aid} · {meta['name']} Agent")
st.caption(meta["desc"])

# 输入区
raw = st.text_area(
    "素材正文",
    key="f_raw",
    height=160,
    placeholder="粘贴你的运营素材、活动说明、数据摘要、用户反馈… 任何你需要 AI 帮你分析或处理的内容。",
    help="D-Agent 会自动从这段文本中提取数字、金额、日期、渠道实体等结构化指标，注入到你的 Agent 上下文中。"
)

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    run_clicked = st.button(
        f"运行 {aid}-Agent",
        type="primary",
        use_container_width=True,
        disabled=not raw.strip(),
    )
with col2:
    mode_label = "LLM · DeepSeek" if effective_use_llm() else "Mock"
    st.caption(f"运行模式：{mode_label}")
with col3:
    st.caption(f"Harness · validate() 开启")

# ── 执行 ──
if run_clicked:
    raw_text = raw.strip()

    # 数据基座：提取指标
    extract_metrics(raw_text)
    metrics_snap = get_cached()

    use_llm = effective_use_llm()
    llm_cfg_val = llm_settings(cfg)

    ctx = {
        "task_id": st.session_state["task_id"],
        "run_id": str(uuid.uuid4()),
        "pack_id": "default",
        "agent_id": aid,
        "brand_voice": "",
        "platforms": ["weibo", "wechat", "xhs"],
        "raw_input": raw_text,
        "structured_metrics": {},
        "upstream": {},
    }

    logs_dir = (ROOT / cfg["paths"]["logs_dir"]).resolve()
    run_id = ctx["run_id"]
    started = time.time()

    # 记录 run
    execute(conn, "INSERT INTO runs (id, task_id, mock, status, started_at) VALUES (?,?,?,?,?)",
            (run_id, st.session_state["task_id"], 1, "running", time.strftime("%Y-%m-%d %H:%M:%S")))

    with st.spinner(f"{aid}-Agent 执行中…"):
        try:
            output = invoke(aid, use_llm=use_llm, context=ctx, llm_cfg=llm_cfg_val, root=ROOT)
            duration_ms = int((time.time() - started) * 1000)

            # 记录步骤
            summary = str(output.get("insights", output.get("segments", output.get("drafts", ""))))[:200]
            execute(conn,
                "INSERT INTO run_steps (run_id, step, status, duration_ms, raw_json, output_summary) VALUES (?,?,?,?,?,?)",
                (run_id, aid, "success", duration_ms, json.dumps(output, ensure_ascii=False), summary))

            append_event(logs_dir, run_id, {"event": "agent_run", "agent": aid, "duration_ms": duration_ms})

            execute(conn, "UPDATE runs SET status=?, finished_at=? WHERE id=?",
                    ("success", time.strftime("%Y-%m-%d %H:%M:%S"), run_id))

            st.session_state["last_result"] = {
                "ok": True,
                "run_id": run_id,
                "agent_id": aid,
                "output": output,
                "duration_ms": duration_ms,
                "metrics_snap": metrics_snap,
            }
        except Exception as e:
            execute(conn, "UPDATE runs SET status=?, finished_at=?, error_message=? WHERE id=?",
                    ("failed", time.strftime("%Y-%m-%d %H:%M:%S"), str(e)[:500], run_id))
            st.session_state["last_result"] = {"ok": False, "error": str(e), "run_id": run_id}

    st.rerun()

# ── 结果展示 ──
res = st.session_state.get("last_result")
if res and res.get("ok"):
    st.divider()

    output = res["output"]
    rid = res["run_id"]

    # Harness 信息条
    st.caption(f"run `{rid[:8]}…` · {res.get('duration_ms', '—')}ms · validate() 已执行 · 日志已写入")

    # Fallback 警告
    if isinstance(output, dict) and output.get("_operai_fallback"):
        st.warning(f"⚠ {output['_operai_fallback']}")

    # 数据基座指标
    snap = res.get("metrics_snap")
    if snap and snap.summary:
        with st.expander("数据基座 · 自动提取指标", expanded=False):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("数字/百分比", len(snap.numbers))
                if snap.numbers:
                    st.caption(", ".join(snap.numbers[:8]))
            with c2:
                st.metric("金额", len(snap.amounts))
                if snap.amounts:
                    st.caption(", ".join(snap.amounts[:5]))
            with c3:
                st.metric("渠道/实体", len(snap.entities))
                if snap.entities:
                    st.caption(", ".join(snap.entities[:8]))

    # Agent 输出
    st.markdown("**Agent 输出**")
    render_output(aid, output)

    # validate() 结果
    st.markdown("**规则校验**")
    try:
        import importlib
        mod = importlib.import_module(f"src.agents.{aid.lower()}_agent")
        validate_fn = getattr(mod, "validate", None)
        if validate_fn:
            issues = validate_fn(output)
            if issues:
                for iss in issues:
                    st.warning(iss)
            else:
                st.success("全部校验通过")
        else:
            st.caption("此 Agent 未定义 validate()")
    except Exception as e:
        st.caption(f"校验执行异常：{e}")

    # 导出
    st.divider()
    st.markdown("**导出方案**")
    if st.button("生成 Campaign Package (Markdown)", type="primary"):
        md = build_campaign_markdown(
            title=f"{aid}-Agent 运营方案",
            task_id=st.session_state["task_id"],
            run_id=rid,
            pack_id="default",
            dag=[aid],
            agent_outputs={aid: output},
        )
        st.download_button(
            "下载方案 (.md)",
            data=md.encode("utf-8"),
            file_name=f"operai-{aid}-{rid[:8]}.md",
            mime="text/markdown",
            use_container_width=True,
        )
        with st.expander("预览"):
            st.code(md, language="markdown")

elif res and not res.get("ok"):
    st.error(res.get("error", "运行失败"))
