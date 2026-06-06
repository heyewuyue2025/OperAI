from __future__ import annotations


def test_role_profiles_define_distinct_deliverable_families() -> None:
    from src.role_deliverables import ROLE_PROFILES, deliverable_for_role

    assert len(ROLE_PROFILES) == 8

    content = deliverable_for_role("content_ops")
    user = deliverable_for_role("user_ops")
    campaign = deliverable_for_role("campaign_ops")
    market = deliverable_for_role("market_ops")

    assert content.family == "content_pack"
    assert user.family == "lifecycle_plan"
    assert campaign.family == "campaign_plan"
    assert market.family == "strategy_report"


def test_role_profiles_only_reference_existing_skills() -> None:
    from src.harness.skill_registry import list_builtin_skills
    from src.role_deliverables import ROLE_PROFILES

    skill_ids = {skill.id for skill in list_builtin_skills()}

    for role_id, profile in ROLE_PROFILES.items():
        missing = set(profile.skills) - skill_ids
        assert not missing, f"{role_id}: {sorted(missing)}"


def test_non_content_roles_do_not_default_to_social_copywriting_or_delivery_package() -> None:
    from src.role_deliverables import ROLE_PROFILES

    copy_first_skills = {"platform_copywriting", "short_video_script", "seo_content_brief", "delivery_package"}
    allowed_copy_roles = {"content_ops", "community_ops"}

    for role_id, profile in ROLE_PROFILES.items():
        skill_ids = set(profile.skills)
        if role_id in allowed_copy_roles:
            continue

        assert not (skill_ids & copy_first_skills), role_id


def test_role_plan_keeps_harness_core_but_uses_role_primary_runners() -> None:
    from src.harness.skill_registry import list_builtin_skills
    from src.role_deliverables import compose_role_plan, deliverable_for_role

    skills = list_builtin_skills()

    user_plan = compose_role_plan("user_ops", "老用户复购下降，需要分层召回和生命周期触达", skills)
    campaign_plan = compose_role_plan("campaign_ops", "新品发布会需要活动策划、渠道节奏和现场执行", skills)
    channel_plan = compose_role_plan("channel_ops", "预算有限，需要安排投放渠道、排期和归因", skills)

    for role_id, plan in {
        "user_ops": user_plan,
        "campaign_ops": campaign_plan,
        "channel_ops": channel_plan,
    }.items():
        plan_ids = [skill.id for skill in plan]
        runners = {skill.runner for skill in plan}
        deliverable = deliverable_for_role(role_id)

        assert plan_ids[0] == "material_intake"
        assert "platform_copywriting" not in plan_ids
        assert "delivery_package" not in plan_ids
        assert deliverable.primary_runner in runners
