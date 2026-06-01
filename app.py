"""OperAI 运营工作台。"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from src.archive_view import build_evidence_chain, list_agent_files, load_run_dossier
from src.export_campaign import build_campaign_docx_bytes, build_campaign_markdown
from src.llm_runtime import effective_use_llm, sync_from_session
from src.harness.plugin_registry import invoke
from src.orchestrator import execute_pipeline, llm_settings_for_run, load_config, open_connection, resolve_paths, upsert_task
from src.render_output import render as render_output
from src.sensitive import effective_sensitive_words, parse_sensitive_lines, save_sensitive_words


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
st.session_state.setdefault("active_agent_id", "C")
st.session_state.setdefault("agent_results", {})
st.session_state.setdefault("operai_force_mock", True)
st.session_state.setdefault("operai_model", "gpt-4o-mini")
st.session_state.setdefault("operai_temperature", float(cfg.get("llm", {}).get("temperature", 0.4)))
st.session_state.setdefault("operai_short_output", False)
st.session_state.setdefault("operai_skip_review", False)
st.session_state.setdefault("operai_split_models", False)
st.session_state.setdefault("operai_model_d", cfg.get("llm", {}).get("model_d", "gpt-4o-mini"))
st.session_state.setdefault("operai_model_c", cfg.get("llm", {}).get("model_c", "gpt-4o"))

sync_from_session(st.session_state)


AGENT_WORKSPACE_META: dict[str, dict[str, Any]] = {
    "D": {
        "focus": "把零散材料先变成事实、指标、洞察和风险清单。",
        "needs": ["活动说明或业务背景", "平台数据、用户反馈、销售数字", "需要特别规避的风险表述"],
        "outputs": ["关键指标与事实摘录", "可传播角度", "风险提示"],
    },
    "U": {
        "focus": "把用户行为和反馈拆成人群、生命周期和触达动作。",
        "needs": ["用户规模、活跃、留存、复购信息", "典型反馈或评论", "当前增长或流失问题"],
        "outputs": ["用户分群", "留存/召回动作", "流失风险判断"],
    },
    "C": {
        "focus": "把洞察转成微博、公众号、小红书等平台可用内容。",
        "needs": ["产品卖点或活动主题", "品牌语气与禁用表达", "目标平台和核心受众"],
        "outputs": ["多平台正文", "标题备选", "短视频口播与合规注记"],
    },
    "A": {
        "focus": "把目标、预算、资源和节奏组织成可执行活动方案。",
        "needs": ["活动目标和时间窗口", "预算或资源约束", "目标人群和关键节点"],
        "outputs": ["活动阶段规划", "任务拆解", "预算与 ROI 假设"],
    },
    "N": {
        "focus": "把内容草案安排到合适的平台、时间窗口和标签策略里。",
        "needs": ["待发布内容", "目标平台", "发布时间限制或活动节奏"],
        "outputs": ["发布排期", "标签建议", "平台注意事项"],
    },
    "F": {
        "focus": "评估渠道效率、预算分配和转化路径。",
        "needs": ["曝光、点击、转化、成本数据", "历史渠道表现", "投放目标"],
        "outputs": ["渠道评分", "预算分配建议", "转化优化提示"],
    },
    "M": {
        "focus": "把品牌、竞品和趋势整理成市场定位判断。",
        "needs": ["品牌信息", "竞品材料", "目标客群和传播目标"],
        "outputs": ["定位建议", "竞品观察", "渠道组合判断"],
    },
    "P": {
        "focus": "把功能数据和用户反馈整理成体验问题与迭代优先级。",
        "needs": ["功能使用数据", "用户评论或客服反馈", "转化漏斗或体验问题"],
        "outputs": ["反馈归类", "体验问题", "迭代优先级"],
    },
    "S": {
        "focus": "把社群语境转成互动话术、活动玩法和 KOL 线索。",
        "needs": ["社群聊天或评论区材料", "活动目标", "潜在 KOL 或用户画像"],
        "outputs": ["互动话术", "社群动作", "KOL 线索"],
    },
    "E": {
        "focus": "把转化漏斗问题转成促销、CTA 和商品页动作。",
        "needs": ["点击、加购、支付、客单价数据", "促销约束", "库存或商品信息"],
        "outputs": ["漏斗诊断", "促销建议", "CTA 变体"],
    },
}


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


def _sidebar_directory(agent_files: dict[str, dict[str, str]], mode_label: str) -> None:
    st.markdown(
        f"""
        <div class="oa-side-head">
          <div class="oa-side-mark">OperAI</div>
          <div class="oa-side-sub">岗位工作台</div>
          <div class="oa-side-case">任务 {st.session_state['task_id'][:8].upper()} / {mode_label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div class='oa-side-section'>岗位目录</div>", unsafe_allow_html=True)
    st.radio(
        "岗位目录",
        options=list(agent_files.keys()),
        format_func=lambda aid: f"{aid} · {agent_files[aid]['title']}",
        key="active_agent_id",
        label_visibility="collapsed",
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


def _current_agent_output(agent_id: str) -> Any:
    stored = st.session_state.get("agent_results", {})
    if isinstance(stored, dict) and agent_id in stored:
        return stored[agent_id]
    outputs = _agent_outputs_for_export(st.session_state.get("last_result"))
    return outputs.get(agent_id)


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


def _run_current_agent(agent_id: str) -> None:
    raw = st.session_state.get("raw_material", "").strip()
    if not raw:
        st.warning("请先为当前岗位提供业务材料。")
        return
    sync_from_session(st.session_state)
    upstream = _agent_outputs_for_export(st.session_state.get("last_result"))
    context = {
        "task_id": st.session_state["task_id"],
        "run_id": str(uuid.uuid4()),
        "agent_id": agent_id,
        "raw_input": raw,
        "brand_voice": st.session_state.get("brand_voice", ""),
        "platforms": st.session_state.get("platforms") or ["weibo", "wechat", "xhs"],
        "pack_id": ARCHIVE_FLOW_ID,
        "upstream": upstream,
    }
    with st.spinner(f"{agent_files[agent_id]['title']}正在处理材料..."):
        output = invoke(
            agent_id,
            use_llm=effective_use_llm(),
            context=context,
            llm_cfg=llm_settings_for_run(cfg),
            root=ROOT,
        )
    results = dict(st.session_state.get("agent_results") or {})
    results[agent_id] = output
    st.session_state["agent_results"] = results
    st.rerun()


agent_files = list_agent_files()
mode_label = "LLM" if effective_use_llm() else "Mock"

with st.sidebar:
    _sidebar_directory(agent_files, mode_label)

active_agent = st.session_state.get("active_agent_id", "C")
agent_meta = agent_files.get(active_agent, agent_files["C"])
workspace_meta = AGENT_WORKSPACE_META.get(active_agent, AGENT_WORKSPACE_META["C"])
st.markdown(
    f"""
    <section class="oa-hero">
      <div>
        <div class="oa-meta">岗位工作台 / {agent_meta['tier']}</div>
        <h1>{agent_meta['title']}工作台</h1>
        <p>{workspace_meta['focus']}</p>
      </div>
      <div>{_stamp(mode_label, "green" if mode_label == "LLM" else "red")}</div>
    </section>
    """,
    unsafe_allow_html=True,
)

input_tab, output_tab, evidence_tab, export_tab, settings_tab = st.tabs(
    ["岗位输入", "产出结果", "证据核查", "交付导出", "运行设置"]
)

with input_tab:
    st.markdown(f"### {agent_meta['title']} · 工作页")
    st.caption("每个岗位都有自己的输入材料、判断重点和交付物。左侧目录切换岗位。")
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
            "这个岗位需要",
            list(workspace_meta["needs"]),
            "输入重点",
        )
        _mini_panel(
            "交付物",
            list(workspace_meta["outputs"]),
            "产出预期",
        )
        c1, c2 = st.columns(2)
        c1.button(
            f"运行{agent_meta['title']}",
            type="primary",
            use_container_width=True,
            on_click=_run_current_agent,
            args=(active_agent,),
        )
        c2.button("运行完整 D-C-N 链路", use_container_width=True, on_click=_run_archive_task)

with output_tab:
    st.markdown(f"### {agent_meta['title']}产出")
    output = _current_agent_output(active_agent)
    if not output:
        st.info(f"还没有{agent_meta['title']}产出。先在「岗位输入」里运行当前岗位。")
    else:
        if isinstance(output, dict):
            render_output(active_agent, output)
        else:
            st.write(output)

with evidence_tab:
    st.markdown("### 证据核查")
    rid = st.session_state.get("active_run_id")
    if not rid:
        st.info("运行完整 D-C-N 链路后，会展示原始素材、指标提取、内容草案、排期建议和导出状态的可追溯链路。")
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
