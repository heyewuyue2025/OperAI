"""Smoke test for newly added domain functions across all agents."""
from __future__ import annotations


def test_d_extract_metrics():
    from src.agents.d_agent import _extract_metrics
    m = _extract_metrics("Q1 GMV 24.8M yuan, YoY +18.6%. douyin grew fastest. Start 2026-06-01.")
    assert len(m["numbers"]) >= 2
    assert len(m["amounts"]) >= 1
    assert len(m["dates"]) >= 1
    assert len(m["entities"]) >= 1


def test_d_scan_risks():
    from src.agents.d_agent import scan_risks
    r = scan_risks("guaranteed return 5%, highest in market, insider says confirmed")
    assert len(r) >= 1


def test_d_validate():
    from src.agents.d_agent import validate
    ok = validate({"insights": ["a"], "risk_flags": ["x"], "evidence_spans": [{"snippet": "test"}]}, raw_input="test")
    assert len(ok) == 0


def test_u_classify_segments():
    from src.agents.u_agent import classify_segments
    s = classify_segments({"active_users": 200, "silent_users": 150, "dormant_users": 300}, 30)
    assert len(s) >= 2


def test_u_determine_lifecycle():
    from src.agents.u_agent import determine_lifecycle
    lc = determine_lifecycle({"has_purchase": True, "activation_done": True, "days_since_signup": 30})
    assert lc == "revenue"


def test_u_validate():
    from src.agents.u_agent import validate
    issues = validate({
        "segments": [{"name": "a", "priority": "high"}, {"name": "b", "priority": "low"}],
        "lifecycle_stage": "retention",
        "retention_actions": [{"segment": "a", "action": "x", "channel": "c"}],
    })
    assert len(issues) == 0


def test_a_build_template():
    from src.agents.a_agent import build_campaign_template
    t = build_campaign_template()
    assert len(t) == 3
    assert t[2]["phase"] == "收尾期"


def test_a_calculate_roi():
    from src.agents.a_agent import calculate_roi_estimate
    roi = calculate_roi_estimate(100000, 500000, 0.04, 386)
    assert "x" in roi["summary"]


def test_a_validate():
    from src.agents.a_agent import build_campaign_template, calculate_roi_estimate, validate
    t = build_campaign_template()
    roi = calculate_roi_estimate(100000, 500000, 0.04, 386)
    issues = validate({"campaign_plan": t, "budget_hints": [{"percent_range": "25%-35%"}], "roi_estimate": roi})
    assert len(issues) == 0


def test_f_score_channels():
    from src.agents.f_agent import score_channels
    chs = [{"channel": "weibo", "roi_score": 70, "audience_match": 80, "cost_efficiency": 60, "scale": 75, "complexity": 30}]
    sc = score_channels(chs)
    assert 0 <= sc[0]["score"] <= 100


def test_f_normalize_budget():
    from src.agents.f_agent import score_channels, normalize_budget
    chs = [{"channel": "weibo", "roi_score": 70, "audience_match": 80, "cost_efficiency": 60, "scale": 75, "complexity": 30}]
    sc = score_channels(chs)
    nb = normalize_budget(sc, 10000)
    assert sum(a["percent"] for a in nb) <= 100


def test_f_validate():
    from src.agents.f_agent import score_channels, normalize_budget, validate
    chs = [{"channel": "weibo", "roi_score": 70, "audience_match": 80, "cost_efficiency": 60, "scale": 75, "complexity": 30}]
    sc = score_channels(chs)
    nb = normalize_budget(sc, 10000)
    issues = validate({"channel_scores": sc, "budget_allocation": nb})
    assert len(issues) == 0


def test_c_cross_platform():
    from src.agents.c_agent import check_cross_platform_consistency
    issues = check_cross_platform_consistency({"weibo": "price 100 yuan", "wechat": "price 200 yuan", "xhs": "price 100 yuan"})
    assert len(issues) >= 1


def test_s_validate():
    from src.agents.s_agent import validate
    issues = validate({
        "community_actions": [
            {"action": "a1", "timing": "t1", "goal": "g1"},
            {"action": "a2", "timing": "t2", "goal": "g2"},
            {"action": "a3", "timing": "t3", "goal": "g3"},
        ],
        "kol_hints": [{"profile": "p", "approach": "a"}],
    })
    assert len(issues) == 0


def test_s_validate_too_few_actions():
    from src.agents.s_agent import validate
    issues = validate({"community_actions": [{"action": "a1", "timing": "t1"}], "kol_hints": []})
    assert any("至少 3 个" in i or "缺少 KOL" in i for i in issues)
