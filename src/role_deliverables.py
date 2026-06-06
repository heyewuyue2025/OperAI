"""Role-aware deliverable model for OperAI Harness.

The workbench should not treat every operations job as social copywriting.
Each role owns a different default deliverable, and Harness uses this map to
choose a useful skill route before the UI renders the run archive.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.harness.skill_registry import SkillSpec, plan_skills


@dataclass(frozen=True)
class RoleProfile:
    id: str
    name: str
    promise: str
    skills: tuple[str, ...]


@dataclass(frozen=True)
class RoleDeliverable:
    role_id: str
    family: str
    title: str
    description: str
    primary_runner: str
    quality_focus: tuple[str, ...]
    output_mode: str


ROLE_PROFILES: dict[str, RoleProfile] = {
    "content_ops": RoleProfile(
        id="content_ops",
        name="内容运营",
        promise="把素材、卖点和用户语境转成可发布、可复核的多平台内容资产。",
        skills=(
            "material_intake",
            "evidence_extraction",
            "platform_copywriting",
            "style_adaptation",
            "seo_content_brief",
            "short_video_script",
            "social_calendar",
            "brand_voice_system",
            "evidence_review",
        ),
    ),
    "user_ops": RoleProfile(
        id="user_ops",
        name="用户运营",
        promise="把用户反馈、行为信号和生命周期问题转成分层触达、召回和留存方案。",
        skills=(
            "material_intake",
            "feedback_synthesis",
            "audience_segmentation",
            "lifecycle_journey",
            "onboarding_flow",
            "retention_winback",
            "voice_of_customer",
            "marketing_automation_nurture",
            "customer_success_health",
            "evidence_review",
        ),
    ),
    "campaign_ops": RoleProfile(
        id="campaign_ops",
        name="活动运营",
        promise="把目标、资源、预算和时间约束整理成可执行活动策划与落地节奏。",
        skills=(
            "material_intake",
            "campaign_architecture",
            "event_webinar_plan",
            "offline_event_ops",
            "channel_calendar",
            "traffic_budgeting",
            "evidence_review",
        ),
    ),
    "channel_ops": RoleProfile(
        id="channel_ops",
        name="渠道运营",
        promise="把资源、内容形态和渠道数据转成分发策略、排期、预算和归因口径。",
        skills=(
            "material_intake",
            "channel_calendar",
            "traffic_budgeting",
            "paid_media_brief",
            "app_store_aso",
            "influencer_collaboration",
            "attribution_plan",
            "dashboard_kpi",
            "evidence_review",
        ),
    ),
    "growth_ops": RoleProfile(
        id="growth_ops",
        name="增长投放",
        promise="围绕流量效率、转化路径和预算约束，生成增长实验与投放优化方案。",
        skills=(
            "material_intake",
            "traffic_budgeting",
            "conversion_cta",
            "landing_page_cro",
            "ab_test_design",
            "ad_creative_testing",
            "growth_loop_design",
            "referral_program",
            "north_star_metric",
            "evidence_review",
        ),
    ),
    "product_ops": RoleProfile(
        id="product_ops",
        name="产品运营",
        promise="把功能数据、体验反馈和用户需求转成产品运营洞察、迭代优先级和验证动作。",
        skills=(
            "material_intake",
            "feedback_synthesis",
            "voice_of_customer",
            "audience_segmentation",
            "positioning_brief",
            "competitive_battlecard",
            "pricing_packaging",
            "evidence_review",
        ),
    ),
    "community_ops": RoleProfile(
        id="community_ops",
        name="社群运营",
        promise="把社群聊天、评论区和 KOL 线索转成互动机制、社群动作和必要的话术素材。",
        skills=(
            "material_intake",
            "feedback_synthesis",
            "community_activation",
            "community_programming",
            "influencer_collaboration",
            "audience_segmentation",
            "style_adaptation",
            "voice_of_customer",
            "evidence_review",
        ),
    ),
    "market_ops": RoleProfile(
        id="market_ops",
        name="市场策略",
        promise="把品牌、竞品、趋势和目标客群整理成市场定位、传播判断和渠道组合报告。",
        skills=(
            "material_intake",
            "positioning_brief",
            "market_research_plan",
            "competitive_battlecard",
            "brand_voice_system",
            "media_outreach",
            "crisis_response",
            "partnership_comarketing",
            "abm_account_plan",
            "evidence_review",
        ),
    ),
}


ROLE_DELIVERABLES: dict[str, RoleDeliverable] = {
    "content_ops": RoleDeliverable(
        role_id="content_ops",
        family="content_pack",
        title="多平台内容资产包",
        description="适合直接进入编辑、审校和发布排期的内容稿件。",
        primary_runner="C",
        quality_focus=("事实一致", "平台适配", "表达口径", "发布风险"),
        output_mode="copy",
    ),
    "user_ops": RoleDeliverable(
        role_id="user_ops",
        family="lifecycle_plan",
        title="用户分层与生命周期运营方案",
        description="给用户运营看的分层、触达、召回和留存行动表。",
        primary_runner="U",
        quality_focus=("分层依据", "触达节奏", "流失风险", "复盘指标"),
        output_mode="plan",
    ),
    "campaign_ops": RoleDeliverable(
        role_id="campaign_ops",
        family="campaign_plan",
        title="活动策划与执行方案",
        description="从目标到阶段、任务、预算和风险的活动落地计划。",
        primary_runner="A",
        quality_focus=("阶段完整", "资源约束", "预算假设", "现场风险"),
        output_mode="plan",
    ),
    "channel_ops": RoleDeliverable(
        role_id="channel_ops",
        family="channel_strategy",
        title="渠道分发与归因方案",
        description="渠道选择、排期、预算分配和效果归因的运营方案。",
        primary_runner="F",
        quality_focus=("渠道匹配", "预算口径", "排期逻辑", "归因指标"),
        output_mode="strategy",
    ),
    "growth_ops": RoleDeliverable(
        role_id="growth_ops",
        family="growth_experiment",
        title="增长实验与转化优化方案",
        description="投放、转化、实验和增长循环的优先级方案。",
        primary_runner="F",
        quality_focus=("增长假设", "实验设计", "转化路径", "停止规则"),
        output_mode="experiment",
    ),
    "product_ops": RoleDeliverable(
        role_id="product_ops",
        family="product_ops_report",
        title="产品运营洞察与迭代报告",
        description="把用户声音、功能信号和市场判断转成产品运营优先级。",
        primary_runner="P",
        quality_focus=("用户证据", "功能影响", "优先级", "验证动作"),
        output_mode="report",
    ),
    "community_ops": RoleDeliverable(
        role_id="community_ops",
        family="community_playbook",
        title="社群运营行动手册",
        description="社群互动机制、话术、KOL 线索和维护节奏。",
        primary_runner="S",
        quality_focus=("人群温度", "互动机制", "话术边界", "社群风险"),
        output_mode="playbook",
    ),
    "market_ops": RoleDeliverable(
        role_id="market_ops",
        family="strategy_report",
        title="市场策略与定位报告",
        description="面向市场与管理层的定位、竞品、传播和渠道组合判断。",
        primary_runner="M",
        quality_focus=("定位清晰", "竞品证据", "渠道组合", "风险处置"),
        output_mode="report",
    ),
}


COPY_FIRST_SKILLS = {
    "platform_copywriting",
    "short_video_script",
    "seo_content_brief",
    "email_campaign",
    "pr_press_release",
    "delivery_package",
}


def profile_for_role(role_id: str) -> RoleProfile:
    return ROLE_PROFILES.get(role_id, ROLE_PROFILES["content_ops"])


def deliverable_for_role(role_id: str) -> RoleDeliverable:
    return ROLE_DELIVERABLES.get(role_id, ROLE_DELIVERABLES["content_ops"])


def role_skill_ids(role_id: str) -> list[str]:
    return list(profile_for_role(role_id).skills)


def role_skills(role_id: str, skills: list[SkillSpec]) -> list[SkillSpec]:
    by_id = {skill.id: skill for skill in skills}
    return [by_id[sid] for sid in role_skill_ids(role_id) if sid in by_id]


def compose_role_plan(role_id: str, task_text: str, skills: list[SkillSpec], *, limit: int = 6) -> list[SkillSpec]:
    role = profile_for_role(role_id)
    deliverable = deliverable_for_role(role_id)
    by_id = {skill.id: skill for skill in skills}
    role_route = [by_id[sid] for sid in role.skills if sid in by_id]
    auto_skills = plan_skills(task_text, limit=limit, root=None)

    allow_copy = role_id in {"content_ops", "community_ops"}
    filtered_auto = [
        skill
        for skill in auto_skills
        if allow_copy or skill.id not in COPY_FIRST_SKILLS
    ]

    merged: dict[str, SkillSpec] = {}
    for skill in [*role_route[:3], *filtered_auto, *role_route[3:]]:
        if not allow_copy and skill.id in COPY_FIRST_SKILLS:
            continue
        merged.setdefault(skill.id, skill)

    plan: list[SkillSpec] = []
    seen_runners: set[str] = set()
    for skill in merged.values():
        runner_key = skill.runner or skill.id
        if runner_key in seen_runners and skill.runner != deliverable.primary_runner:
            continue
        if runner_key in seen_runners:
            continue
        seen_runners.add(runner_key)
        plan.append(skill)
        if len(plan) >= limit:
            break
    return plan


def build_role_deliverable(role_id: str, results: dict[str, Any]) -> dict[str, Any]:
    deliverable = deliverable_for_role(role_id)
    payloads = {
        str(item.get("runner") or "").upper(): item.get("payload") or {}
        for item in results.values()
        if isinstance(item, dict)
    }
    d_out = payloads.get("D", {})
    primary = payloads.get(deliverable.primary_runner, {})

    sections = _sections_for_family(deliverable.family, payloads, primary)
    if not sections:
        sections = [{"title": "交付摘要", "items": _fallback_items(d_out, primary)}]

    return {
        "title": deliverable.title,
        "description": deliverable.description,
        "family": deliverable.family,
        "output_mode": deliverable.output_mode,
        "primary_runner": deliverable.primary_runner,
        "quality_focus": list(deliverable.quality_focus),
        "sections": sections,
    }


def quality_score_for_role(role_id: str, results: dict[str, Any]) -> dict[str, Any]:
    deliverable = deliverable_for_role(role_id)
    skill_count = len(results)
    completed_runners = {
        str(item.get("runner") or "").upper()
        for item in results.values()
        if isinstance(item, dict)
    }
    completed_ids = set(results.keys())
    has_evidence = bool(completed_ids & {"material_intake", "evidence_extraction", "evidence_review"}) or "D" in completed_runners
    has_primary = deliverable.primary_runner in completed_runners
    has_review = bool(completed_ids & {"evidence_review", "data_quality_audit"}) or has_evidence

    score = min(100, 38 + skill_count * 8 + int(has_evidence) * 18 + int(has_primary) * 22 + int(has_review) * 10)
    issues: list[str] = []
    if not has_evidence:
        issues.append("建议先完成材料结构化或证据摘录，避免方案脱离输入事实。")
    if not has_primary:
        issues.append(f"建议运行主交付智能体 {deliverable.primary_runner}，形成「{deliverable.title}」。")
    if not has_review:
        issues.append("建议补充质量复核，检查证据、边界、风险和可执行性。")
    if not issues:
        issues = [f"当前链路已覆盖「{deliverable.title}」的核心复核点：{'、'.join(deliverable.quality_focus)}。"]
    return {"score": score, "issues": issues, "deliverable": deliverable.title}


def _sections_for_family(family: str, payloads: dict[str, dict[str, Any]], primary: dict[str, Any]) -> list[dict[str, Any]]:
    d_out = payloads.get("D", {})
    u_out = payloads.get("U", {})
    a_out = payloads.get("A", {})
    c_out = payloads.get("C", {})
    f_out = payloads.get("F", {})
    e_out = payloads.get("E", {})
    p_out = payloads.get("P", {})
    m_out = payloads.get("M", {})
    s_out = payloads.get("S", {})
    n_out = payloads.get("N", {})

    if family == "content_pack":
        return [
            {"title": "内容主稿", "layout": "wide_copy", "items": _draft_items(c_out.get("drafts") or {})},
            {"title": "标题与口播", "items": [*(c_out.get("title_variants") or []), c_out.get("short_video_script", "")]},
            {"title": "发布节奏", "items": n_out.get("schedule_suggestions") or []},
        ]
    if family == "lifecycle_plan":
        return [
            {"title": "用户分层", "items": u_out.get("segments") or primary.get("segments") or []},
            {"title": "生命周期判断", "items": [u_out.get("lifecycle_stage") or primary.get("lifecycle_stage") or "待确认"]},
            {"title": "触达与召回动作", "items": u_out.get("retention_actions") or primary.get("retention_actions") or []},
            {"title": "流失风险", "items": u_out.get("churn_risks") or primary.get("churn_risks") or []},
        ]
    if family == "campaign_plan":
        return [
            {"title": "活动阶段", "items": a_out.get("campaign_plan") or primary.get("campaign_plan") or []},
            {"title": "预算与资源", "items": a_out.get("budget_hints") or primary.get("budget_hints") or []},
            {"title": "ROI 假设", "items": [a_out.get("roi_estimate") or primary.get("roi_estimate") or {}]},
        ]
    if family == "channel_strategy":
        return [
            {"title": "渠道评分", "items": f_out.get("channel_scores") or []},
            {"title": "预算分配", "items": f_out.get("budget_allocation") or []},
            {"title": "排期与归因", "items": [*(n_out.get("schedule_suggestions") or []), *(d_out.get("insights") or [])]},
        ]
    if family == "growth_experiment":
        return [
            {"title": "增长假设", "items": m_out.get("channel_mix") or d_out.get("angles") or []},
            {"title": "投放与预算", "items": f_out.get("budget_allocation") or f_out.get("channel_scores") or []},
            {"title": "转化优化", "items": [*(e_out.get("funnel_steps") or []), *(e_out.get("cta_variants") or [])]},
        ]
    if family == "product_ops_report":
        return [
            {"title": "功能洞察", "items": p_out.get("feature_insights") or primary.get("feature_insights") or []},
            {"title": "体验信号", "items": p_out.get("ux_signals") or primary.get("ux_signals") or []},
            {"title": "迭代建议", "items": p_out.get("iteration_hints") or primary.get("iteration_hints") or []},
        ]
    if family == "community_playbook":
        return [
            {"title": "社群动作", "items": s_out.get("community_actions") or primary.get("community_actions") or []},
            {"title": "KOL 与共创", "items": s_out.get("kol_hints") or primary.get("kol_hints") or []},
            {"title": "互动话术", "items": s_out.get("engagement_scripts") or primary.get("engagement_scripts") or []},
        ]
    if family == "strategy_report":
        return [
            {"title": "市场定位", "items": [m_out.get("positioning") or primary.get("positioning") or "待确认"]},
            {"title": "竞品与机会", "items": m_out.get("competitive_notes") or primary.get("competitive_notes") or []},
            {"title": "渠道组合", "items": m_out.get("channel_mix") or primary.get("channel_mix") or []},
        ]
    return [{"title": "交付摘要", "items": _fallback_items(d_out, primary)}]


def _dict_values(value: dict[str, Any]) -> list[Any]:
    return [item for item in value.values() if item]


def _draft_items(value: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"platform": str(platform), "body": str(body), "preview": _preview_text(str(body))}
        for platform, body in value.items()
        if str(body).strip()
    ]


def _preview_text(text: str, limit: int = 96) -> str:
    compact = " ".join(text.strip().split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _fallback_items(*payloads: dict[str, Any]) -> list[Any]:
    items: list[Any] = []
    for payload in payloads:
        for value in payload.values():
            if isinstance(value, list):
                items.extend(value[:3])
            elif isinstance(value, (str, dict)):
                items.append(value)
            if len(items) >= 5:
                return items
    return items
