"""OperAI 运营工作台。"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from src.archive_view import build_archive_summary, build_evidence_chain, list_agent_files, load_run_dossier
from src.export_campaign import build_campaign_docx_bytes, build_campaign_markdown
from src.llm_runtime import effective_use_llm, sync_from_session
from src.orchestrator import execute_pipeline, load_config, open_connection, resolve_paths, upsert_task
from src.render_output import render as render_output
from src.sensitive import effective_sensitive_words, parse_sensitive_lines, save_sensitive_words
from src.storage.db import query_all


load_dotenv()

ROOT = Path(__file__).resolve().parent
cfg = load_config(ROOT)
conn = open_connection(ROOT, cfg)
_db_path, LOGS_DIR = resolve_paths(ROOT, cfg)

ARCHIVE_FLOW_ID = "archive"

st.set_page_config(page_title="OperAI 运营工作台", layout="wide")

_theme_path = ROOT / "frontend" / "streamlit-theme.css"
if _theme_path.is_file():
    st.markdown(f"<style>{_theme_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

st.session_state.setdefault("task_id", str(uuid.uuid4()))
st.session_state.setdefault("task_title", "未命名运营任务")
st.session_state.setdefault("raw_material", "")
st.session_state.setdefault("brand_voice", "")
st.session_state.setdefault("platforms", ["weibo", "wechat", "xhs"])
st.session_state.setdefault("last_result", None)
st.session_state.setdefault("active_run_id", None)
st.session_state.setdefault("operai_force_mock", True)
st.session_state.setdefault("operai_model", "gpt-4o-mini")
st.session_state.setdefault("operai_temperature", float(cfg.get("llm", {}).get("temperature", 0.4)))
st.session_state.setdefault("operai_short_output", False)
st.session_state.setdefault("operai_skip_review", False)
st.session_state.setdefault("operai_split_models", False)
st.session_state.setdefault("operai_model_d", cfg.get("llm", {}).get("model_d", "gpt-4o-mini"))
st.session_state.setdefault("operai_model_c", cfg.get("llm", {}).get("model_c", "gpt-4o"))

sync_from_session(st.session_state)


def _stamp(label: str, tone: str = "red") -> str:
    return f"<span class='oa-stamp oa-{tone}'>{label}</span>"


def _card(title: str, body: str, meta: str = "") -> None:
    st.markdown(
        f"""
        <div class="oa-card">
          <div class="oa-meta">{meta}</div>
          <h3>{title}</h3>
          <p>{body}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _mini_panel(title: str, items: list[str], meta: str = "") -> None:
    body = "".join(f"<li>{item}</li>" for item in items)
    st.markdown(
        f"""
        <div class="oa-mini-panel">
          <div class="oa-meta">{meta}</div>
          <h3>{title}</h3>
          <ul>{body}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _workflow_bar(active: int = 1) -> None:
    steps = [
        ("01", "录入任务", "素材、平台、表达口径"),
        ("02", "运行链路", "D 提取 / C 生成 / N 排期"),
        ("03", "复核结果", "输出、风险、状态"),
        ("04", "交付导出", "Markdown / Word"),
    ]
    cols = st.columns(4, gap="small")
    for idx, (num, title, desc) in enumerate(steps, start=1):
        with cols[idx - 1]:
            state = "is-active" if idx == active else ""
            st.markdown(
                f"<div class='oa-work-step {state}'><b>{num}</b><span>{title}</span><small>{desc}</small></div>",
                unsafe_allow_html=True,
            )


def _sidebar_status(summary: dict[str, Any], mode_label: str) -> None:
    metrics = [
        ("智能体", summary["agent_count"]),
        ("运行", summary["run_count"]),
        ("任务", summary["task_count"]),
        ("日志", summary["log_count"]),
    ]
    rows = "".join(f"<div><span>{label}</span><strong>{value}</strong></div>" for label, value in metrics)
    st.markdown(
        f"""
        <div class="oa-side-head">
          <div class="oa-side-mark">OperAI</div>
          <div class="oa-side-sub">运营工作台</div>
          <div class="oa-side-case">任务 {st.session_state['task_id'][:8].upper()} / {mode_label}</div>
        </div>
        <div class="oa-side-rail">{rows}</div>
        """,
        unsafe_allow_html=True,
    )


def _zh_status(value: Any) -> str:
    return {
        "ready": "可用",
        "stub": "Mock 可用",
        "missing": "缺失",
        "success": "成功",
        "failed": "失败",
        "running": "运行中",
        "need_review": "待复核",
        "captured": "已捕获",
        "implicit": "已推断",
        "blocked": "阻断",
    }.get(str(value), str(value))


def _recent_runs(limit: int = 8) -> list[dict[str, Any]]:
    rows = query_all(
        conn,
        "SELECT id, task_id, status, mock, started_at, finished_at, pack_id FROM runs ORDER BY datetime(started_at) DESC LIMIT ?",
        (limit,),
    )
    return [dict(r) for r in rows]


def _agent_outputs_for_export(result: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not result:
        return {}
    if isinstance(result.get("agent_outputs"), dict):
        return result["agent_outputs"]
    out: dict[str, dict[str, Any]] = {}
    for aid in ("D", "C", "N"):
        key = f"{aid.lower()}_out"
        if isinstance(result.get(key), dict):
            out[aid] = result[key]
    return out


def _run_archive_task() -> None:
    raw = st.session_state.get("raw_material", "").strip()
    if not raw:
        st.warning("请先粘贴运营素材、活动说明或用户反馈。")
        return
    sync_from_session(st.session_state)
    upsert_task(
        conn,
        task_id=st.session_state["task_id"],
        title=st.session_state["task_title"].strip() or "未命名运营任务",
        brand_voice=st.session_state.get("brand_voice", ""),
        platforms=st.session_state.get("platforms") or ["weibo", "wechat", "xhs"],
        raw_input=raw,
        pack_id=ARCHIVE_FLOW_ID,
    )
    started = time.time()
    with st.spinner("正在提取关键信息、生成内容方案、匹配平台排期..."):
        result = execute_pipeline(
            ROOT,
            conn,
            cfg,
            task_id=st.session_state["task_id"],
            title=st.session_state["task_title"].strip() or "未命名运营任务",
            brand_voice=st.session_state.get("brand_voice", ""),
            platforms=st.session_state.get("platforms") or ["weibo", "wechat", "xhs"],
            raw_input=raw,
        )
    result["duration_ms"] = int((time.time() - started) * 1000)
    st.session_state["last_result"] = result
    if result.get("run_id"):
        st.session_state["active_run_id"] = result["run_id"]
    st.rerun()


agent_files = list_agent_files()
summary = build_archive_summary(conn, LOGS_DIR)
mode_label = "LLM" if effective_use_llm() else "Mock"

with st.sidebar:
    _sidebar_status(summary, mode_label)
    st.markdown("<div class='oa-side-section'>最近运行</div>", unsafe_allow_html=True)
    for run in _recent_runs(6):
        label = f"{run['id'][:8]} · {_zh_status(run['status'])}"
        if st.button(label, key=f"side_run_{run['id']}", use_container_width=True):
            st.session_state["active_run_id"] = run["id"]
            st.rerun()

st.markdown(
    f"""
    <section class="oa-hero">
      <div>
        <div class="oa-meta">运营情报 / 任务工作流</div>
        <h1>运营任务控制台</h1>
        <p>把活动说明、产品卖点、用户反馈和平台数据，转成可复核的内容方案、发布排期与交付文档。</p>
      </div>
      <div>{_stamp(mode_label, "green" if mode_label == "LLM" else "red")}</div>
    </section>
    """,
    unsafe_allow_html=True,
)

_workflow_bar(1 if not st.session_state.get("active_run_id") else 3)

task_tab, agent_tab, run_tab, evidence_tab, export_tab, settings_tab = st.tabs(
    ["任务输入", "智能体编排", "结果复盘", "证据核查", "交付导出", "运行设置"]
)

with task_tab:
    st.markdown("### 任务输入")
    st.caption("先把业务上下文填清楚。系统会按 D -> C -> N 链路依次完成信息提取、内容生成和平台排期。")
    left, right = st.columns([0.64, 0.36], gap="large")
    with left:
        st.text_input("任务名称", key="task_title", placeholder="例如：EchoPods Pro 新品上市战役")
        st.text_area(
            "输入材料",
            key="raw_material",
            height=260,
            placeholder="粘贴活动说明、产品卖点、用户反馈、渠道数据、竞品观察或任何需要转化成运营方案的材料。",
        )
        st.text_area("表达口径", key="brand_voice", height=88, placeholder="例如：克制可信、年轻活泼、专业权威；或写明禁用词、语气边界。")
    with right:
        st.multiselect(
            "目标平台",
            options=["weibo", "wechat", "xhs", "douyin", "bilibili"],
            key="platforms",
        )
        _mini_panel(
            "本次会产出",
            [
                "D：提取指标、事实、风险信号",
                "C：生成多平台文案与标题",
                "N：给出发布时间、标签和平台注意事项",
            ],
            "输出预览",
        )
        _mini_panel(
            "运行前检查",
            [
                "材料越具体，方案越稳",
                "平台至少选择一个",
                "表达口径会约束文案风格",
            ],
            "准备状态",
        )
        st.button("生成运营方案", type="primary", use_container_width=True, on_click=_run_archive_task)

with agent_tab:
    st.markdown("### 智能体编排")
    st.caption("这里展示每个 Agent 在链路中的职责。当前默认执行 D -> C -> N，其他 Agent 保留为可扩展岗位。")
    cols = st.columns(2)
    for idx, (aid, meta) in enumerate(agent_files.items()):
        with cols[idx % 2]:
            st.markdown(
                f"""
                <div class="oa-agent-card">
                  <div class="oa-agent-code">{aid}</div>
                  <div>
                    <div class="oa-meta">{meta['tier']} / {_zh_status(meta['status'])}</div>
                    <h3>{meta['title']}</h3>
                    <p>{meta['archive_role']}</p>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

with run_tab:
    st.markdown("### 结果复盘")
    rid = st.session_state.get("active_run_id")
    if not rid:
        st.info("还没有运行结果。先在「任务输入」里生成一次运营方案。")
    else:
        dossier = load_run_dossier(conn, LOGS_DIR, rid)
        if not dossier:
            st.error("找不到这次运行记录。")
        else:
            h1, h2, h3 = st.columns(3)
            h1.metric("状态", _zh_status(dossier["status"]))
            h2.metric("模式", "模拟" if dossier["mock"] else "LLM")
            h3.metric("完成步骤", len(dossier["steps"]))
            st.markdown(f"<div class='oa-run-id'>RUN {rid}</div>", unsafe_allow_html=True)
            st.markdown("#### 执行链路")
            for step in dossier["steps"]:
                st.markdown(
                    f"<div class='oa-step'><b>{step['step']}</b><span>{_zh_status(step['status'])}</span><small>{step.get('duration_ms') or 0} ms</small></div>",
                    unsafe_allow_html=True,
                )
            outputs = dossier.get("agent_outputs") or {}
            st.markdown("#### Agent 输出")
            for aid, output in outputs.items():
                with st.expander(f"{aid} · {agent_files.get(aid, {}).get('title', '智能体')}输出", expanded=aid == "C"):
                    if isinstance(output, dict):
                        render_output(aid, output)
                    else:
                        st.write(output)

with evidence_tab:
    st.markdown("### 证据核查")
    rid = st.session_state.get("active_run_id")
    if not rid:
        st.info("运行后会展示原始素材、指标提取、内容草案、排期建议和导出状态的可追溯链路。")
    else:
        chain = build_evidence_chain(conn, LOGS_DIR, rid)
        cols = st.columns(len(chain["nodes"]))
        for idx, node in enumerate(chain["nodes"]):
            with cols[idx]:
                tone = "green" if node["status"] in {"ready", "captured"} else "red"
                st.markdown(
                    f"<div class='oa-trace-node'><b>{idx + 1:02d}</b><span>{node['label']}</span>{_stamp(_zh_status(node['status']), tone)}</div>",
                    unsafe_allow_html=True,
                )
        with st.expander("运行日志尾部", expanded=True):
            events = chain.get("trace_events") or []
            if events:
                st.json(events)
            else:
                st.caption("暂无轨迹事件。")

with export_tab:
    st.markdown("### 交付导出")
    result = st.session_state.get("last_result")
    rid = st.session_state.get("active_run_id") or (result or {}).get("run_id")
    if not rid:
        st.info("暂无可导出的方案。生成一次运营方案后，可在这里下载 Markdown 或 Word。")
    else:
        dossier = load_run_dossier(conn, LOGS_DIR, rid)
        agent_outputs = dossier.get("agent_outputs") or _agent_outputs_for_export(result)
        dag = list(agent_outputs.keys()) or ["D", "C", "N"]
        md = build_campaign_markdown(
            title=st.session_state.get("task_title", "OperAI 运营方案"),
            task_id=dossier.get("task_id", st.session_state["task_id"]),
            run_id=rid,
            pack_id=dossier.get("pack_id", ARCHIVE_FLOW_ID),
            dag=dag,
            agent_outputs=agent_outputs,
        )
        st.download_button("下载 Markdown 方案", md.encode("utf-8"), file_name=f"operai-plan-{rid[:8]}.md", mime="text/markdown", use_container_width=True)
        try:
            docx_bytes = build_campaign_docx_bytes(
                title=st.session_state.get("task_title", "OperAI 运营方案"),
                task_id=dossier.get("task_id", st.session_state["task_id"]),
                run_id=rid,
                pack_id=dossier.get("pack_id", ARCHIVE_FLOW_ID),
                dag=dag,
                agent_outputs=agent_outputs,
            )
            st.download_button(
                "下载 Word 方案",
                docx_bytes,
                file_name=f"operai-plan-{rid[:8]}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Word 导出暂不可用：{exc}")
        with st.expander("Markdown 预览"):
            st.code(md, language="markdown")

with settings_tab:
    st.markdown("### 运行设置")
    left, right = st.columns(2, gap="large")
    with left:
        st.checkbox("强制 Mock 模式", key="operai_force_mock")
        st.checkbox("缩短输出", key="operai_short_output")
        st.checkbox("跳过人工复核", key="operai_skip_review")
        st.checkbox("D/C 分模型", key="operai_split_models")
        st.text_input("默认模型", key="operai_model")
        st.text_input("D 模型", key="operai_model_d")
        st.text_input("C 模型", key="operai_model_c")
        st.slider("温度", min_value=0.0, max_value=1.2, step=0.05, key="operai_temperature")
        if st.button("应用运行设置", type="primary"):
            sync_from_session(st.session_state)
            st.success("运行设置已应用。")
    with right:
        words = effective_sensitive_words(ROOT, st.session_state)
        text = st.text_area("敏感词", value="\n".join(words), height=260)
        c1, c2 = st.columns(2)
        if c1.button("本次会话使用", use_container_width=True):
            st.session_state["operai_sensitive_words"] = parse_sensitive_lines(text)
            st.success("会话敏感词已更新。")
        if c2.button("保存到文件", use_container_width=True):
            save_sensitive_words(ROOT, parse_sensitive_lines(text))
            st.success("敏感词已保存。")
