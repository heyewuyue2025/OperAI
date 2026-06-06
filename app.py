"""OperAI Harness 工作台。"""
from __future__ import annotations

import json
import os
import time
import uuid
from html import escape
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from src.display_labels import label_key, label_value
from src.harness.plugin_registry import invoke
from src.harness.skill_registry import (
    SkillSpec,
    build_skill_from_form,
    list_skills,
    save_custom_skill,
)
from src.llm_runtime import effective_use_llm, sync_from_session
from src.orchestrator import llm_settings_for_run, load_config, open_connection, resolve_paths
from src.render_output import render as render_output
from src.role_deliverables import (
    ROLE_PROFILES,
    build_role_deliverable,
    compose_role_plan,
    deliverable_for_role,
    profile_for_role,
    quality_score_for_role,
    role_skill_ids,
    role_skills,
)
from src.sensitive import effective_sensitive_words, parse_sensitive_lines, save_sensitive_words
from src.voice_styles import VOICE_STYLE_PRESETS, merge_voice_styles


load_dotenv()

ROOT = Path(__file__).resolve().parent
cfg = load_config(ROOT)
conn = open_connection(ROOT, cfg)
_db_path, LOGS_DIR = resolve_paths(ROOT, cfg)

st.set_page_config(page_title="OperAI Harness 工作台", layout="wide")

_theme_path = ROOT / "frontend" / "streamlit-theme.css"
if _theme_path.is_file():
    st.markdown(f"<style>{_theme_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

st.session_state.setdefault("task_id", str(uuid.uuid4()))
st.session_state.setdefault("task_title", "未命名运营任务")
st.session_state.setdefault("raw_material", "")
st.session_state.setdefault("brand_voice", "")
st.session_state.setdefault("voice_style_presets", [])
st.session_state.setdefault("platforms_cn", ["微博", "微信公众号", "小红书", "哔哩哔哩", "抖音", "快手"])
st.session_state.setdefault("active_role_id", "content_ops")
st.session_state.setdefault("active_skill_id", "platform_copywriting")
st.session_state.setdefault("skill_results", {})
st.session_state.setdefault("active_run_id", None)
st.session_state.setdefault("last_skill_plan", [])
st.session_state.setdefault("operai_force_mock", not bool(os.getenv("OPENAI_API_KEY", "").strip()))
st.session_state.setdefault("operai_model", os.getenv("OPENAI_MODEL", "deepseek-v4-pro"))
st.session_state.setdefault("operai_temperature", float(cfg.get("llm", {}).get("temperature", 0.4)))
st.session_state.setdefault("operai_short_output", True)
st.session_state.setdefault("operai_skip_review", False)
st.session_state.setdefault("operai_split_models", False)
st.session_state.setdefault("operai_model_d", cfg.get("llm", {}).get("model_d", "deepseek-v4-pro"))
st.session_state.setdefault("operai_model_c", cfg.get("llm", {}).get("model_c", "deepseek-v4-pro"))
st.session_state.setdefault("operai_api_base_url", os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com"))
st.session_state.setdefault("operai_api_key_input", "")

sync_from_session(st.session_state)

PLATFORM_OPTIONS: dict[str, str] = {
    "微博": "weibo",
    "微信公众号": "wechat",
    "小红书": "xhs",
    "哔哩哔哩": "bilibili",
    "抖音": "douyin",
    "快手": "kuaishou",
}

ALL_PLATFORM_LABELS = list(PLATFORM_OPTIONS.keys())
st.session_state["platforms_cn"] = ALL_PLATFORM_LABELS


def _selected_platform_ids() -> list[str]:
    return list(PLATFORM_OPTIONS.values())


def _mask_secret(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return "未配置"
    if len(value) <= 10:
        return "已配置"
    return f"{value[:3]}…{value[-4:]}"


def _save_env_values(updates: dict[str, str]) -> None:
    env_path = ROOT / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            out.append(line)
            continue
        key, _value = line.split("=", 1)
        if key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={value}")
    env_path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _apply_api_config(*, persist: bool) -> None:
    api_key = (st.session_state.get("operai_api_key_input") or "").strip()
    base_url = (st.session_state.get("operai_api_base_url") or "").strip()
    model = (st.session_state.get("operai_model") or "").strip()

    updates: dict[str, str] = {}
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
        updates["OPENAI_API_KEY"] = api_key
        st.session_state["operai_force_mock"] = False
    if base_url:
        os.environ["OPENAI_BASE_URL"] = base_url
        updates["OPENAI_BASE_URL"] = base_url
    if model:
        os.environ["OPENAI_MODEL"] = model
        updates["OPENAI_MODEL"] = model
    os.environ["OPERAI_MOCK"] = "1" if st.session_state.get("operai_force_mock") else ""
    updates["OPERAI_MOCK"] = os.environ["OPERAI_MOCK"]

    sync_from_session(st.session_state)
    if persist and updates:
        _save_env_values(updates)


def _apply_voice_style_presets() -> None:
    st.session_state["brand_voice"] = merge_voice_styles(
        st.session_state.get("brand_voice", ""),
        st.session_state.get("voice_style_presets", []),
    )


def _stamp(label: str, tone: str = "red") -> str:
    return f"<span class='oa-stamp oa-{tone}'>{label}</span>"


def _e(value: Any) -> str:
    return escape(str(value), quote=True)


def _category_counts(skills: list[SkillSpec]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for skill in skills:
        counts[skill.category] = counts.get(skill.category, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _skill_card(skill: SkillSpec, *, active: bool = False) -> None:
    css = "oa-agent-card oa-skill-card is-active" if active else "oa-agent-card oa-skill-card"
    st.markdown(
        f"""
        <div class="{css}">
          <div class="oa-agent-code">{_e(skill.id[:2].upper())}</div>
          <div>
            <div class="oa-meta">{_e(skill.category)} / {_e(skill.source)}</div>
            <h3>{_e(skill.name)}</h3>
            <p>{_e(skill.description)}</p>
            <div class="oa-skill-meta">输入：{_e('、'.join(skill.inputs[:3]))}<br>输出：{_e('、'.join(skill.outputs[:3]))}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _mini_panel(title: str, items: list[str], meta: str = "") -> None:
    body = "".join(f"<li>{_e(item)}</li>" for item in items)
    st.markdown(
        f"""
        <div class="oa-mini-panel">
          <div class="oa-meta">{_e(meta)}</div>
          <h3>{_e(title)}</h3>
          <ul>{body}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _metric_strip(skills: list[SkillSpec], planned: list[SkillSpec], results: dict[str, Any]) -> str:
    items = [
        ("职能入口", "8", "按运营岗位进入"),
        ("运营智能体", "10", "保留原有执行集群"),
        ("可组合 Skill", str(len(skills)), "覆盖公司级运营知识"),
        ("本次编排", str(len(planned)), f"已完成 {len(results)} 个节点"),
    ]
    cards = "".join(
        f"<div class='oa-metric-card'><span>{_e(label)}</span><strong>{_e(value)}</strong><small>{_e(note)}</small></div>"
        for label, value, note in items
    )
    return f"<div class='oa-metric-strip'>{cards}</div>"


def _harness_flow(planned: list[SkillSpec], results: dict[str, Any]) -> str:
    stages = [
        ("任务理解", "读取材料、目标、平台和约束"),
        ("Skill 匹配", "从 Skill Registry 选择可执行能力"),
        ("Harness 编排", "安排上下文传递、顺序和依赖"),
        ("质量检验", "复核证据、风险、平台适配和交付完整度"),
    ]
    nodes = "".join(
        f"<div class='oa-flow-node'><b>{idx:02d}</b><strong>{_e(title)}</strong><span>{_e(desc)}</span></div>"
        for idx, (title, desc) in enumerate(stages, start=1)
    )
    names = " / ".join(skill.name for skill in planned[:4])
    if len(planned) > 4:
        names += f" / +{len(planned) - 4}"
    if not names:
        names = "等待任务材料"
    return (
        "<div class='oa-flow-board'>"
        f"<div class='oa-flow-head'><span>Harness Run Plan</span><strong>{len(planned)} 个 Skill · {len(results)} 个已完成</strong></div>"
        f"<div class='oa-flow-grid'>{nodes}</div>"
        f"<div class='oa-flow-foot'>{_e(names)}</div>"
        "</div>"
    )


def _plan_panel(planned: list[SkillSpec], active_skill: SkillSpec, results: dict[str, Any]) -> str:
    rows = []
    for idx, skill in enumerate(planned, start=1):
        status = "已完成" if skill.id in results else ("当前" if skill.id == active_skill.id else "待运行")
        tone = "done" if skill.id in results else ("active" if skill.id == active_skill.id else "queued")
        rows.append(
            f"<div class='oa-plan-row is-{tone}'><b>{idx:02d}</b><span><strong>{_e(skill.name)}</strong><small>{_e(skill.category)} · {_e(status)}</small></span></div>"
        )
    return (
        "<div class='oa-harness-panel'>"
        "<div class='oa-panel-head'><span>Harness 编排建议</span><strong>本次推荐链路</strong></div>"
        f"<div class='oa-plan-list'>{''.join(rows)}</div>"
        "<p>系统会根据当前职能、任务材料和关键词选择 Skill，并自动形成可执行顺序。用户选择职能后不需要逐个挑 Skill。</p>"
        "</div>"
    )


def _skill_universe(skills: list[SkillSpec]) -> str:
    counts = list(_category_counts(skills).items())[:10]
    chips = "".join(f"<span>{_e(name)} <b>{count}</b></span>" for name, count in counts)
    return (
        "<div class='oa-skill-universe'>"
        f"<div><p class='oa-meta'>Skill Registry</p><h3>{len(skills)} 个运营 Skill 已接入 Harness</h3></div>"
        f"<div class='oa-skill-chips'>{chips}</div>"
        "</div>"
    )


def _deliverable_item_text(item: Any) -> str:
    if isinstance(item, dict):
        parts = [
            f"{label_key(key)}：{_deliverable_item_text(value)}"
            for key, value in item.items()
            if not str(key).startswith("_")
        ]
        return "；".join(parts)
    if isinstance(item, list):
        return "、".join(_deliverable_item_text(value) for value in item)
    return label_value(item).strip()


def _role_deliverable_panel(role_id: str, results: dict[str, Any]) -> str:
    bundle = build_role_deliverable(role_id, results)
    focus = "".join(f"<span>{_e(item)}</span>" for item in bundle["quality_focus"])
    sections = []
    for section in bundle["sections"]:
        items = [item for item in section.get("items", []) if _deliverable_item_text(item)]
        if not items:
            items = ["等待该职能主智能体补齐。"]
        rows = "".join(
            f"<li><b>{idx:02d}</b><span>{_e(_deliverable_item_text(item))}</span></li>"
            for idx, item in enumerate(items[:5], start=1)
        )
        sections.append(
            f"<div class='oa-deliverable-section'><h4>{_e(section.get('title', '交付模块'))}</h4><ol>{rows}</ol></div>"
        )
    return (
        "<div class='oa-deliverable'>"
        "<div class='oa-deliverable-head'>"
        f"<span>{_e(label_value(bundle['output_mode']))} / {bundle['primary_runner']}-Agent</span>"
        f"<h3>{_e(bundle['title'])}</h3>"
        f"<p>{_e(bundle['description'])}</p>"
        f"<div class='oa-deliverable-focus'>{focus}</div>"
        "</div>"
        f"<div class='oa-deliverable-grid'>{''.join(sections)}</div>"
        "</div>"
    )


def _sidebar_skill_stack(role_skills: list[SkillSpec]) -> str:
    rows = "".join(
        f"<li><b>{idx:02d}</b><span>{_e(skill.name)}</span><small>{_e(skill.category)}</small></li>"
        for idx, skill in enumerate(role_skills, start=1)
    )
    return f"<ol class='oa-side-skill-stack'>{rows}</ol>"


def _sidebar_directory(skills: list[SkillSpec], mode_label: str) -> None:
    st.markdown(
        f"""
        <div class="oa-side-head">
          <div class="oa-side-mark">OperAI</div>
          <div class="oa-side-sub">Harness 工作台</div>
          <a class="oa-home-link" href="http://127.0.0.1:8080" target="_self">
            <span>返回产品首页</span>
            <b>↗</b>
          </a>
          <div class="oa-side-stats">
            <span><b>8</b>职能</span>
            <span><b>10</b>智能体</span>
            <span><b>{len(skills)}</b>Skill</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div class='oa-side-section'>职能入口</div>", unsafe_allow_html=True)
    st.radio(
        "职能入口",
        options=list(ROLE_PROFILES.keys()),
        format_func=lambda rid: ROLE_PROFILES[rid].name,
        key="active_role_id",
        label_visibility="collapsed",
    )
    role_skill_ids = _role_skill_ids(st.session_state["active_role_id"])
    st.session_state["active_skill_id"] = role_skill_ids[0]
    st.markdown("<div class='oa-side-section'>自动编排 Skill</div>", unsafe_allow_html=True)
    st.markdown(_sidebar_skill_stack(_role_skills(st.session_state["active_role_id"], skills)), unsafe_allow_html=True)


def _format_skill_option(skill_id: str, skills: list[SkillSpec]) -> str:
    skill = _skill_lookup(skills).get(skill_id)
    if skill is None:
        return skill_id
    return f"{skill.name}"


def _skill_lookup(skills: list[SkillSpec]) -> dict[str, SkillSpec]:
    return {skill.id: skill for skill in skills}


def _role_skill_ids(role_id: str) -> list[str]:
    return role_skill_ids(role_id)


def _role_skills(role_id: str, skills: list[SkillSpec]) -> list[SkillSpec]:
    return role_skills(role_id, skills)


def _compose_role_plan(role_id: str, task_text: str, skills: list[SkillSpec]) -> list[SkillSpec]:
    return compose_role_plan(role_id, task_text, skills, limit=6)


def _current_task_text() -> str:
    return "\n".join(
        [
            st.session_state.get("task_title", ""),
            st.session_state.get("raw_material", ""),
            st.session_state.get("brand_voice", ""),
            " ".join(st.session_state.get("platforms_cn") or []),
        ]
    ).strip()


def _invoke_skill(skill: SkillSpec, *, fast_route: bool = False) -> dict[str, Any]:
    raw = st.session_state.get("raw_material", "").strip()
    if not raw:
        raise ValueError("请先粘贴运营素材、活动说明或用户反馈。")

    started = time.time()
    run_id = st.session_state.get("active_run_id") or str(uuid.uuid4())
    st.session_state["active_run_id"] = run_id

    context = {
        "task_id": st.session_state["task_id"],
        "run_id": run_id,
        "skill_id": skill.id,
        "agent_id": skill.runner,
        "pack_id": "harness",
        "raw_input": raw,
        "brand_voice": st.session_state.get("brand_voice", ""),
        "platforms": _selected_platform_ids() or ["weibo", "wechat", "xhs"],
        "upstream": {
            sid: item.get("payload", {})
            for sid, item in (st.session_state.get("skill_results") or {}).items()
            if isinstance(item, dict)
        },
    }
    for _sid, item in (st.session_state.get("skill_results") or {}).items():
        if not isinstance(item, dict):
            continue
        runner_id = str(item.get("runner") or "").upper()
        if runner_id:
            context["upstream"][runner_id] = item.get("payload", {})

    runner_use_llm = effective_use_llm()
    primary_runner = deliverable_for_role(st.session_state.get("active_role_id", "content_ops")).primary_runner
    if fast_route and skill.runner not in {"D", primary_runner}:
        runner_use_llm = False

    if skill.runner:
        payload = invoke(
            skill.runner,
            use_llm=runner_use_llm,
            context=context,
            llm_cfg=llm_settings_for_run(cfg),
            root=ROOT,
        )
        if fast_route and not runner_use_llm and effective_use_llm():
            payload["_operai_fast_route"] = "Harness 快速链路：该节点使用规则引擎生成，避免重复等待模型。"
    else:
        payload = {
            "summary": f"{skill.name} 已根据当前任务生成一份结构化草案。",
            "inputs": skill.inputs,
            "outputs": skill.outputs,
            "checks": skill.checks,
            "_operai_custom_skill": True,
        }

    return {
        "skill": skill.to_dict(),
        "runner": skill.runner,
        "payload": payload,
        "duration_ms": int((time.time() - started) * 1000),
        "status": "success",
    }


def _run_selected_skill(skill_id: str, skills: list[SkillSpec]) -> None:
    skill = _skill_lookup(skills)[skill_id]
    try:
        result = _invoke_skill(skill)
    except ValueError as exc:
        st.warning(str(exc))
        return
    results = dict(st.session_state.get("skill_results") or {})
    results[skill.id] = result
    st.session_state["skill_results"] = results


def _run_planned_skills(planned: list[SkillSpec]) -> None:
    if not planned:
        st.warning("当前任务还没有可运行的 Skill 计划。")
        return
    st.session_state["active_run_id"] = str(uuid.uuid4())
    st.session_state["skill_results"] = {}
    results: dict[str, Any] = {}
    try:
        for skill in planned:
            results[skill.id] = _invoke_skill(skill, fast_route=True)
            st.session_state["skill_results"] = dict(results)
    except ValueError as exc:
        st.warning(str(exc))
        return
    st.session_state["skill_results"] = results
    st.session_state["last_skill_plan"] = [skill.id for skill in planned]


def _quality_score(results: dict[str, Any], role_id: str | None = None) -> dict[str, Any]:
    return quality_score_for_role(role_id or st.session_state.get("active_role_id", "content_ops"), results)


def _build_skill_markdown(results: dict[str, Any]) -> str:
    lines = [
        f"# {st.session_state.get('task_title', 'OperAI 运营方案')}",
        "",
        f"> Run: {st.session_state.get('active_run_id') or 'session'}",
        "> Engine: OperAI Harness Engine",
        "",
    ]
    for idx, item in enumerate(results.values(), start=1):
        skill = item.get("skill", {})
        payload = item.get("payload", {})
        lines.append(f"## {idx}. {skill.get('name', 'Skill 输出')}")
        lines.append("")
        if isinstance(payload, dict):
            lines.append("```json")
            lines.append(json.dumps(payload, ensure_ascii=False, indent=2))
            lines.append("```")
        else:
            lines.append(str(payload))
        lines.append("")
    quality = _quality_score(results)
    lines.append("## 质量评估")
    lines.append("")
    lines.append(f"- 综合评分：{quality['score']}/100")
    lines.append(f"- 目标交付：{quality.get('deliverable', '运营交付物')}")
    for issue in quality["issues"]:
        lines.append(f"- {issue}")
    return "\n".join(lines)


skills = list_skills(ROOT)
skills_by_id = _skill_lookup(skills)
if not skills:
    st.error("Skill Registry 为空，请检查配置。")
    st.stop()
mode_label = "LLM" if effective_use_llm() else "Mock"

with st.sidebar:
    _sidebar_directory(skills, mode_label)

active_role = profile_for_role(st.session_state["active_role_id"])
active_deliverable = deliverable_for_role(st.session_state["active_role_id"])
planned_skills = _compose_role_plan(st.session_state["active_role_id"], _current_task_text(), skills)
active_skill = planned_skills[0] if planned_skills else skills_by_id.get(st.session_state.get("active_skill_id", ""), skills[0])
st.session_state["active_skill_id"] = active_skill.id
results = st.session_state.get("skill_results") or {}

st.markdown(
    f"""
    <section class="oa-hero oa-harness-hero">
      <div>
        <div class="oa-meta">OperAI Harness / 职能编排中枢</div>
        <h1>{active_role.name}工作台</h1>
        <p>{active_role.promise} 默认交付「{active_deliverable.title}」，Harness 会负责选择 Skill、组织执行顺序、传递上下文并把结果送进质量检验。</p>
      </div>
      <div>{_stamp(mode_label, "green" if mode_label == "LLM" else "red")}</div>
    </section>
    """,
    unsafe_allow_html=True,
)
st.markdown(_metric_strip(skills, planned_skills, results), unsafe_allow_html=True)
st.markdown(_harness_flow(planned_skills, results), unsafe_allow_html=True)

task_tab, run_tab, quality_tab, skill_tab, studio_tab, settings_tab = st.tabs(
    ["任务编排", "运行档案", "质量检验", "Skill 能力图谱", "Skill Studio", "运行设置"]
)

with task_tab:
    st.markdown("### 任务编排")
    st.caption(f"当前职能：{active_role.name}。先把业务上下文讲清楚，系统会按这个职能推荐一组可执行 Skill，并记录每一步的输入、输出和复核要求。")
    left, right = st.columns([0.58, 0.42], gap="large")
    with left:
        st.markdown("<div class='oa-field-title'>任务上下文</div>", unsafe_allow_html=True)
        st.text_input("任务名称", key="task_title", placeholder="例如：EchoPods Pro 新品上市运营方案")
        st.text_area(
            "输入材料",
            key="raw_material",
            height=300,
            placeholder="粘贴活动说明、产品卖点、用户反馈、渠道数据、竞品观察或任何需要转化成运营方案的材料。",
        )
        st.markdown("<div class='oa-field-title'>表达风格词库</div>", unsafe_allow_html=True)
        st.multiselect(
            "选择表达风格",
            options=list(VOICE_STYLE_PRESETS),
            key="voice_style_presets",
            placeholder="可多选，例如：克制可信、清晰直接、用户同理心",
            label_visibility="collapsed",
        )
        st.button(
            "写入表达口径",
            key="apply_voice_style_presets",
            use_container_width=True,
            on_click=_apply_voice_style_presets,
        )
        st.text_area(
            "表达口径",
            key="brand_voice",
            height=140,
            placeholder="例如：克制可信、年轻活泼、专业权威；也可以写禁用词、风险边界、品牌称呼、必须保留的说法。这里不需要填写平台名称，Harness 会按当前职能决定交付格式。",
        )
    with right:
        st.markdown(_plan_panel(planned_skills, active_skill, results), unsafe_allow_html=True)
        _mini_panel("当前 Skill 需要", active_skill.inputs, active_skill.category)
        _mini_panel("当前 Skill 交付", active_skill.outputs, "输出预期")
        c1, c2 = st.columns(2)
        c1.button(
            "只运行第一步",
            use_container_width=True,
            on_click=_run_selected_skill,
            args=(active_skill.id, skills),
        )
        c2.button(
            "运行 Harness 链路",
            type="primary",
            use_container_width=True,
            on_click=_run_planned_skills,
            args=(planned_skills,),
        )

with skill_tab:
    st.markdown("### Skill 能力图谱")
    st.caption("这里同步展示全部 Skill。运营用户从职能入口进入，Harness 在背后从完整 Skill Registry 里组合能力。")
    st.markdown(_skill_universe(skills), unsafe_allow_html=True)
    filter_col, search_col = st.columns([0.35, 0.65], gap="medium")
    categories = ["全部"] + list(_category_counts(skills).keys())
    with filter_col:
        selected_category = st.selectbox("能力分类", categories)
    with search_col:
        skill_query = st.text_input("搜索 Skill", placeholder="例如：召回、SEO、线索评分、活动、证据")
    filtered_skills = skills
    if selected_category != "全部":
        filtered_skills = [skill for skill in filtered_skills if skill.category == selected_category]
    if skill_query.strip():
        query = skill_query.strip().lower()
        filtered_skills = [
            skill
            for skill in filtered_skills
            if query in " ".join([skill.name, skill.category, skill.description, *skill.keywords]).lower()
        ]
    st.caption(f"当前显示 {len(filtered_skills)} / {len(skills)} 个 Skill。左侧「自动编排 Skill」会按当前职能锁定推荐，不需要用户逐个选择。")
    cols = st.columns(2, gap="large")
    current_role_skills = _role_skills(st.session_state["active_role_id"], skills)
    role_ids = {item.id for item in current_role_skills}
    display_skills = sorted(
        filtered_skills,
        key=lambda skill: (0 if skill.id in role_ids else 1, skill.category, skill.name),
    )
    for idx, skill in enumerate(display_skills):
        with cols[idx % 2]:
            _skill_card(skill, active=skill.id == active_skill.id)

with run_tab:
    st.markdown("### 运行档案")
    results = st.session_state.get("skill_results") or {}
    if not results:
        st.info("还没有运行记录。先在「任务输入」中运行一个 Skill 或推荐计划。")
    else:
        total_ms = sum(int(item.get("duration_ms", 0)) for item in results.values() if isinstance(item, dict))
        st.markdown(
            f"""
            <div class="oa-run-summary">
              <span>Run ID</span><strong>{_e(st.session_state.get('active_run_id') or 'session')}</strong>
              <span>已完成节点</span><strong>{len(results)}</strong>
              <span>总耗时</span><strong>{total_ms} ms</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(_role_deliverable_panel(st.session_state["active_role_id"], results), unsafe_allow_html=True)
        st.markdown("#### Skill 节点记录")
        for sid, item in results.items():
            skill = item.get("skill", {})
            payload = item.get("payload", {})
            st.markdown(
                f"""
                <div class="oa-run-record">
                  <div>
                    <span>{_e(skill.get('category', ''))}</span>
                    <strong>{_e(skill.get('name', sid))}</strong>
                  </div>
                  <small>{int(item.get('duration_ms', 0))} ms / {_e(label_value(item.get('status', 'success')))}</small>
                </div>
                """,
                unsafe_allow_html=True,
            )
            runner = item.get("runner")
            if runner and isinstance(payload, dict):
                render_output(runner, payload, key_prefix=f"run_{sid}")
            else:
                st.json(payload)
            st.markdown("<div class='oa-run-gap'></div>", unsafe_allow_html=True)

with quality_tab:
    st.markdown("### Harness 质量检验")
    results = st.session_state.get("skill_results") or {}
    if not results:
        st.info("运行 Skill 后，Harness 会在这里给出证据覆盖、平台适配、风险检查和交付完整度建议。")
    else:
        quality = _quality_score(results)
        score_col, gate_col = st.columns([0.28, 0.72], gap="large")
        with score_col:
            st.metric("Harness 质量评分", f"{quality['score']}/100")
        with gate_col:
            _mini_panel(f"{quality.get('deliverable', '交付物')}复核", quality["issues"], "质量检验")
        st.markdown("#### 执行链路")
        for idx, (sid, item) in enumerate(results.items(), start=1):
            skill = item.get("skill", {})
            st.markdown(
                f"<div class='oa-step'><b>{idx:02d}</b><span>{skill.get('name', sid)}</span><small>{skill.get('category', '')} / {label_value(item.get('status', 'success'))}</small></div>",
                unsafe_allow_html=True,
            )
        st.markdown("#### 交付导出")
        st.caption("复核完成后再导出运行记录，避免在任务编排、能力图谱和设置页出现无关交付按钮。")
        st.download_button(
            "下载 Harness 运行 Markdown",
            _build_skill_markdown(results).encode("utf-8"),
            file_name=f"operai-harness-{(st.session_state.get('active_run_id') or 'session')[:8]}.md",
            mime="text/markdown",
            use_container_width=True,
        )

with studio_tab:
    st.markdown("### Skill Studio")
    st.caption("给客户预留新增 Skill 的口子。新增后会进入左侧 Skill 目录和 Skill 库。")
    left, right = st.columns(2, gap="large")
    with left:
        new_name = st.text_input("Skill 名称", placeholder="例如：私域老客召回策略")
        new_category = st.text_input("分类", placeholder="例如：用户增长")
        new_description = st.text_area("能力说明", height=90, placeholder="这个 Skill 解决什么运营问题？")
        new_keywords = st.text_area("触发关键词", height=74, placeholder="每行一个，例如：老客\n召回\n私域")
    with right:
        new_inputs = st.text_area("输入字段", height=90, placeholder="每行一个，例如：用户等级\n历史消费\n流失信号")
        new_outputs = st.text_area("输出字段", height=90, placeholder="每行一个，例如：分层策略\n触达话术\n复盘指标")
        new_checks = st.text_area("质量检查", height=90, placeholder="每行一个，例如：不能过度打扰\n必须给出复盘指标")
        if st.button("保存 Skill", type="primary", use_container_width=True):
            try:
                skill = build_skill_from_form(
                    name=new_name,
                    category=new_category,
                    description=new_description,
                    inputs_text=new_inputs,
                    outputs_text=new_outputs,
                    checks_text=new_checks,
                    keywords_text=new_keywords,
                )
                save_custom_skill(ROOT, skill)
                st.session_state["active_skill_id"] = skill.id
                st.success(f"已保存 Skill：{skill.name}")
                st.rerun()
            except ValueError as exc:
                st.warning(str(exc))

with settings_tab:
    st.markdown("### 运行设置")
    api_col, runtime_col = st.columns([0.54, 0.46], gap="large")
    with api_col:
        st.markdown("#### API 接入")
        st.caption(f"当前连接：{_mask_secret(os.getenv('OPENAI_API_KEY', ''))} / {os.getenv('OPENAI_BASE_URL', '未设置')}")
        st.text_input("API Base URL", key="operai_api_base_url", placeholder="例如：https://api.deepseek.com")
        st.text_input("默认模型", key="operai_model", placeholder="例如：deepseek-v4-pro")
        st.text_input(
            "API Key",
            key="operai_api_key_input",
            type="password",
            placeholder="留空则沿用当前已配置 Key；填写后可应用或保存",
        )
        api_a, api_b = st.columns(2)
        if api_a.button("本次会话使用 API", type="primary", use_container_width=True):
            _apply_api_config(persist=False)
            st.success("API 配置已应用到本次会话。")
            st.rerun()
        if api_b.button("保存到 .env", use_container_width=True):
            _apply_api_config(persist=True)
            st.success("API 配置已保存到 .env，并已应用。")
            st.rerun()

    with runtime_col:
        st.markdown("#### 运行参数")
        st.checkbox("强制 Mock 模式", key="operai_force_mock")
        st.checkbox("缩短输出", key="operai_short_output")
        st.checkbox("跳过人工复核", key="operai_skip_review")
        st.checkbox("启用技能分流模型", key="operai_split_models")
        st.text_input("轻量技能模型", key="operai_model_d")
        st.text_input("生成技能模型", key="operai_model_c")
        st.slider("温度", min_value=0.0, max_value=1.2, step=0.05, key="operai_temperature")
        if st.button("应用运行设置", type="primary"):
            os.environ["OPERAI_MOCK"] = "1" if st.session_state.get("operai_force_mock") else ""
            sync_from_session(st.session_state)
            st.success("运行设置已应用。")

    st.markdown("#### 敏感词")
    left, right = st.columns(2, gap="large")
    with left:
        words = effective_sensitive_words(ROOT, st.session_state)
        text = st.text_area("敏感词", value="\n".join(words), height=260)
        c1, c2 = st.columns(2)
        if c1.button("本次会话使用", use_container_width=True):
            st.session_state["operai_sensitive_words"] = parse_sensitive_lines(text)
            st.success("会话敏感词已更新。")
        if c2.button("保存到文件", use_container_width=True):
            save_sensitive_words(ROOT, parse_sensitive_lines(text))
            st.success("敏感词已保存。")
