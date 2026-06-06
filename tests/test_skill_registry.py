from __future__ import annotations

import json
from pathlib import Path


def test_builtin_skills_cover_harness_workflow() -> None:
    from src.harness.skill_registry import list_builtin_skills

    skills = list_builtin_skills()
    ids = {skill.id for skill in skills}

    assert len(skills) >= 50
    assert "material_intake" in ids
    assert "platform_copywriting" in ids
    assert "seo_keyword_map" in ids
    assert "email_campaign" in ids
    assert "lead_scoring" in ids
    assert "customer_success_health" in ids
    assert "crisis_response" in ids
    assert "evidence_review" in ids
    assert "delivery_package" in ids
    assert all(skill.inputs for skill in skills)
    assert all(skill.outputs for skill in skills)


def test_plan_skills_prefers_relevant_operational_capabilities() -> None:
    from src.harness.skill_registry import plan_skills

    planned = plan_skills(
        "我们要做小红书新品种草，需要提炼用户反馈、生成平台文案、安排发布时间并检查敏感表达。",
        limit=5,
    )
    ids = [skill.id for skill in planned]

    assert "feedback_synthesis" in ids
    assert "platform_copywriting" in ids
    assert "channel_calendar" in ids
    assert "evidence_review" in ids


def test_plan_skills_covers_growth_and_revops_language() -> None:
    from src.harness.skill_registry import plan_skills

    planned = plan_skills(
        "我们要做B2B线索培育、CRM数据清洗、线索评分和付费投放归因看板。",
        limit=8,
    )
    ids = {skill.id for skill in planned}

    assert "lead_scoring" in ids
    assert "crm_data_hygiene" in ids
    assert "marketing_automation_nurture" in ids
    assert "attribution_plan" in ids


def test_custom_skill_roundtrip(tmp_path: Path) -> None:
    from src.harness.skill_registry import SkillSpec, list_skills, save_custom_skill

    skill = SkillSpec(
        id="vip_retention_playbook",
        name="VIP 留存策略",
        category="用户增长",
        description="把高价值用户反馈转成分层触达策略。",
        inputs=["用户等级", "历史消费", "流失信号"],
        outputs=["分层策略", "触达话术", "复盘指标"],
        checks=["触达频率不能过高", "必须给出复盘指标"],
        keywords=["vip", "留存", "召回"],
        runner="U",
        source="custom",
    )

    save_custom_skill(tmp_path, skill)
    loaded = [item for item in list_skills(tmp_path) if item.id == "vip_retention_playbook"]

    assert len(loaded) == 1
    assert loaded[0].source == "custom"
    assert loaded[0].outputs[-1] == "复盘指标"

    raw = json.loads((tmp_path / "data" / "custom_skills.json").read_text(encoding="utf-8"))
    assert raw[0]["id"] == "vip_retention_playbook"
