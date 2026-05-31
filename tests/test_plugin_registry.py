"""插件注册表：D/C/N Mock invoke 与契约键名。"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPERAI_MOCK", "1")


def _minimal_context(*, agent_id: str = "D", upstream: dict | None = None) -> dict:
    return {
        "task_id": str(uuid.uuid4()),
        "run_id": str(uuid.uuid4()),
        "pack_id": "media",
        "agent_id": agent_id,
        "brand_voice": "克制",
        "platforms": ["weibo", "xhs"],
        "raw_input": "校园音乐节预热，强调安全与包容。",
        "upstream": upstream or {},
    }


def test_list_plugins_includes_dcn() -> None:
    from src.harness.plugin_registry import list_plugins

    ids = {p.agent_id for p in list_plugins()}
    assert {"D", "C", "N"}.issubset(ids)
    by_id = {p.agent_id: p for p in list_plugins()}
    assert by_id["D"].status == "ready"
    assert by_id["C"].status == "ready"
    assert by_id["N"].status == "ready"


def test_invoke_d_mock_has_required_keys() -> None:
    from src.harness.plugin_registry import invoke

    ctx = _minimal_context(agent_id="D")
    out = invoke("D", use_llm=False, context=ctx, llm_cfg={}, root=ROOT)
    for key in ("insights", "angles", "risk_flags", "evidence_spans"):
        assert key in out


def test_invoke_unknown_agent_raises() -> None:
    from src.harness.plugin_registry import invoke

    with pytest.raises(KeyError, match="Unknown agent_id"):
        invoke("Z", use_llm=False, context=_minimal_context(), llm_cfg={})
