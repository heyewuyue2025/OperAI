"""十 Agent Mock invoke 契约键名（agent-plugin-contract.md）。"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from src.agents.base import AGENT_IDS

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "D": ("insights", "angles", "risk_flags", "evidence_spans"),
    "U": ("segments", "lifecycle_stage", "retention_actions"),
    "C": ("drafts", "title_variants"),
    "A": ("campaign_plan", "budget_hints", "roi_estimate"),
    "P": ("feature_insights", "ux_signals", "iteration_hints"),
    "M": ("positioning", "competitive_notes", "channel_mix"),
    "F": ("channel_scores", "budget_allocation", "conversion_hints"),
    "N": ("schedule_suggestions", "hashtags", "platform_notes"),
    "S": ("community_actions", "kol_hints", "engagement_scripts"),
    "E": ("funnel_steps", "promo_suggestions", "cta_variants"),
}


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPERAI_MOCK", "1")


def _context_for(agent_id: str) -> dict:
    upstream: dict = {}
    if agent_id in ("C", "U", "A", "P", "M", "F", "S", "E"):
        upstream["D"] = {
            "insights": ["测试洞察"],
            "angles": ["测试角度"],
            "risk_flags": [],
            "evidence_spans": [{"field": "raw_input", "snippet": "测试"}],
        }
    if agent_id == "N":
        upstream["C"] = {
            "drafts": {"weibo": "测试微博文案"},
            "title_variants": ["标题A", "标题B"],
        }
        upstream["D"] = upstream.get("D") or {"insights": ["测试"]}
    return {
        "task_id": str(uuid.uuid4()),
        "run_id": str(uuid.uuid4()),
        "pack_id": "archive",
        "agent_id": agent_id,
        "brand_voice": "克制",
        "platforms": ["weibo", "xhs"],
        "raw_input": "新品冷萃杯上市契约测试素材。",
        "upstream": upstream,
    }


@pytest.mark.parametrize("agent_id", AGENT_IDS)
def test_invoke_mock_has_required_keys(agent_id: str) -> None:
    from src.harness.plugin_registry import invoke

    out = invoke(agent_id, use_llm=False, context=_context_for(agent_id), llm_cfg={}, root=ROOT)
    for key in REQUIRED_KEYS[agent_id]:
        assert key in out, f"{agent_id} missing {key}"


def test_list_plugins_ten_with_status() -> None:
    from src.harness.plugin_registry import list_plugins

    plugins = list_plugins()
    assert len(plugins) == 10
    by_id = {p.agent_id: p for p in plugins}
    assert by_id["D"].status == "ready"
    assert by_id["U"].status == "ready"
