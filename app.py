"""OperAI Archive Desk.

The workbench treats every operation as an archive record: Task File, Agent
Index, Run Dossier, Evidence Chain, Export Vault, and Settings.
"""
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
from src.harness.pack_loader import list_packs
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

st.set_page_config(page_title="OperAI Archive Desk", layout="wide")

_theme_path = ROOT / "frontend" / "streamlit-theme.css"
if _theme_path.is_file():
    st.markdown(f"<style>{_theme_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

st.session_state.setdefault("task_id", str(uuid.uuid4()))
st.session_state.setdefault("task_title", "Untitled Task File")
st.session_state.setdefault("raw_material", "")
st.session_state.setdefault("brand_voice", "")
st.session_state.setdefault("platforms", ["weibo", "wechat", "xhs"])
st.session_state.setdefault("selected_pack", cfg.get("harness", {}).get("default_pack_id", "media"))
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
        st.warning("Task File 缺少原始素材。")
        return
    sync_from_session(st.session_state)
    selected_pack = st.session_state.get("selected_pack", cfg.get("harness", {}).get("default_pack_id", "media"))
    upsert_task(
        conn,
        task_id=st.session_state["task_id"],
        title=st.session_state["task_title"].strip() or "Untitled Task File",
        brand_voice=st.session_state.get("brand_voice", ""),
        platforms=st.session_state.get("platforms") or ["weibo", "wechat", "xhs"],
        raw_input=raw,
        pack_id=selected_pack,
    )
    started = time.time()
    with st.spinner("Archive Desk 正在装配案卷、扫描证据链、运行 DAG..."):
        result = execute_pipeline(
            ROOT,
            conn,
            cfg,
            task_id=st.session_state["task_id"],
            title=st.session_state["task_title"].strip() or "Untitled Task File",
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
    st.markdown("<div class='oa-sidebar-title'>OperAI<br/>Archive Desk</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='oa-meta'>CASE {st.session_state['task_id'][:8].upper()} / {mode_label}</div>", unsafe_allow_html=True)
    st.divider()
    c1, c2 = st.columns(2)
    c1.metric("Agents", summary["agent_count"])
    c2.metric("Runs", summary["run_count"])
    c3, c4 = st.columns(2)
    c3.metric("Tasks", summary["task_count"])
    c4.metric("Logs", summary["log_count"])
    st.divider()
    st.caption("Recent Run Dossiers")
    for run in _recent_runs(6):
        label = f"{run['id'][:8]} · {run['status']}"
        if st.button(label, key=f"side_run_{run['id']}", use_container_width=True):
            st.session_state["active_run_id"] = run["id"]
            st.rerun()

st.markdown(
    f"""
    <section class="oa-hero">
      <div>
        <div class="oa-meta">OPERATIONS INTELLIGENCE / ARCHIVE OS</div>
        <h1>Campaign Dossier Desk</h1>
        <p>创建 Task File，运行 Agent DAG，审阅 Run Dossier 与 Evidence Chain，最后归档导出。</p>
      </div>
      <div>{_stamp(mode_label, "green" if mode_label == "LLM" else "red")}</div>
    </section>
    """,
    unsafe_allow_html=True,
)

task_tab, agent_tab, run_tab, evidence_tab, export_tab, settings_tab = st.tabs(
    ["Task File", "Agent Index", "Run Dossier", "Evidence Chain", "Export Vault", "Settings"]
)

with task_tab:
    st.markdown("### Task File")
    left, right = st.columns([0.68, 0.32], gap="large")
    with left:
        st.text_input("Archive title", key="task_title", placeholder="例如：EchoPods Pro 新品上市战役")
        st.text_area(
            "Raw material",
            key="raw_material",
            height=240,
            placeholder="粘贴活动说明、产品卖点、用户反馈、渠道数据或任意运营素材。",
        )
        st.text_area("Brand voice", key="brand_voice", height=90, placeholder="克制可信、年轻活泼、专业权威...")
    with right:
        packs = [p.id for p in list_packs(ROOT)]
        current_pack = st.session_state.get("selected_pack", "media")
        st.selectbox("Industry Pack", options=packs, index=packs.index(current_pack) if current_pack in packs else 0, key="selected_pack")
        st.multiselect(
            "Platforms",
            options=["weibo", "wechat", "xhs", "douyin", "bilibili"],
            default=st.session_state.get("platforms", ["weibo", "wechat", "xhs"]),
            key="platforms",
        )
        _card("Default DAG", "D -> C -> N 会生成指标、洞察、内容和渠道排期，并写入 Run Dossier。", "PACK ROUTE")
        st.button("Run Archive File", type="primary", use_container_width=True, on_click=_run_archive_task)

with agent_tab:
    st.markdown("### Agent Index")
    cols = st.columns(2)
    for idx, (aid, meta) in enumerate(agent_files.items()):
        with cols[idx % 2]:
            st.markdown(
                f"""
                <div class="oa-agent-card">
                  <div class="oa-agent-code">{aid}</div>
                  <div>
                    <div class="oa-meta">{meta['tier']} / {meta['status']}</div>
                    <h3>{meta['title']}</h3>
                    <p>{meta['archive_role']}</p>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

with run_tab:
    st.markdown("### Run Dossier")
    rid = st.session_state.get("active_run_id")
    if not rid:
        st.info("尚未选择或生成 Run Dossier。先在 Task File 运行一次。")
    else:
        dossier = load_run_dossier(conn, LOGS_DIR, rid)
        if not dossier:
            st.error("Run Dossier 不存在。")
        else:
            h1, h2, h3, h4 = st.columns(4)
            h1.metric("Status", dossier["status"])
            h2.metric("Mode", "Mock" if dossier["mock"] else "LLM")
            h3.metric("Pack", dossier.get("pack_id", "media"))
            h4.metric("Steps", len(dossier["steps"]))
            st.markdown(f"<div class='oa-run-id'>RUN {rid}</div>", unsafe_allow_html=True)
            for step in dossier["steps"]:
                st.markdown(
                    f"<div class='oa-step'><b>{step['step']}</b><span>{step['status']}</span><small>{step.get('duration_ms') or 0} ms</small></div>",
                    unsafe_allow_html=True,
                )
            outputs = dossier.get("agent_outputs") or {}
            for aid, output in outputs.items():
                with st.expander(f"{aid} · {agent_files.get(aid, {}).get('title', 'Agent')} Output", expanded=aid == "C"):
                    if isinstance(output, dict):
                        render_output(aid, output)
                    else:
                        st.write(output)

with evidence_tab:
    st.markdown("### Evidence Chain")
    rid = st.session_state.get("active_run_id")
    if not rid:
        st.info("运行后会显示证据链、节点状态和 JSONL trace。")
    else:
        chain = build_evidence_chain(conn, LOGS_DIR, rid)
        cols = st.columns(len(chain["nodes"]))
        for idx, node in enumerate(chain["nodes"]):
            with cols[idx]:
                tone = "green" if node["status"] in {"ready", "captured"} else "red"
                st.markdown(
                    f"<div class='oa-trace-node'><b>{idx + 1:02d}</b><span>{node['label']}</span>{_stamp(node['status'], tone)}</div>",
                    unsafe_allow_html=True,
                )
        with st.expander("JSONL Trace Tail", expanded=True):
            events = chain.get("trace_events") or []
            if events:
                st.json(events)
            else:
                st.caption("No trace events found.")

with export_tab:
    st.markdown("### Export Vault")
    result = st.session_state.get("last_result")
    rid = st.session_state.get("active_run_id") or (result or {}).get("run_id")
    if not rid:
        st.info("暂无可导出的归档物。")
    else:
        dossier = load_run_dossier(conn, LOGS_DIR, rid)
        agent_outputs = dossier.get("agent_outputs") or _agent_outputs_for_export(result)
        dag = list(agent_outputs.keys()) or ["D", "C", "N"]
        md = build_campaign_markdown(
            title=st.session_state.get("task_title", "OperAI Archive File"),
            task_id=dossier.get("task_id", st.session_state["task_id"]),
            run_id=rid,
            pack_id=dossier.get("pack_id", st.session_state.get("selected_pack", "media")),
            dag=dag,
            agent_outputs=agent_outputs,
        )
        st.download_button("Download Markdown Dossier", md.encode("utf-8"), file_name=f"operai-dossier-{rid[:8]}.md", mime="text/markdown", use_container_width=True)
        try:
            docx_bytes = build_campaign_docx_bytes(
                title=st.session_state.get("task_title", "OperAI Archive File"),
                task_id=dossier.get("task_id", st.session_state["task_id"]),
                run_id=rid,
                pack_id=dossier.get("pack_id", st.session_state.get("selected_pack", "media")),
                dag=dag,
                agent_outputs=agent_outputs,
            )
            st.download_button(
                "Download Word Dossier",
                docx_bytes,
                file_name=f"operai-dossier-{rid[:8]}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Word export unavailable: {exc}")
        with st.expander("Markdown Preview"):
            st.code(md, language="markdown")

with settings_tab:
    st.markdown("### Settings")
    left, right = st.columns(2, gap="large")
    with left:
        st.checkbox("Force Mock mode", key="operai_force_mock")
        st.checkbox("Short output", key="operai_short_output")
        st.checkbox("Skip human review", key="operai_skip_review")
        st.checkbox("Split models for D/C", key="operai_split_models")
        st.text_input("Default model", key="operai_model")
        st.text_input("D model", key="operai_model_d")
        st.text_input("C model", key="operai_model_c")
        st.slider("Temperature", min_value=0.0, max_value=1.2, step=0.05, key="operai_temperature")
        if st.button("Apply runtime settings", type="primary"):
            sync_from_session(st.session_state)
            st.success("Runtime settings applied.")
    with right:
        words = effective_sensitive_words(ROOT, st.session_state)
        text = st.text_area("Sensitive words", value="\n".join(words), height=260)
        c1, c2 = st.columns(2)
        if c1.button("Use In Session", use_container_width=True):
            st.session_state["operai_sensitive_words"] = parse_sensitive_lines(text)
            st.success("Session sensitive list updated.")
        if c2.button("Save To File", use_container_width=True):
            save_sensitive_words(ROOT, parse_sensitive_lines(text))
            st.success("Sensitive words saved.")
