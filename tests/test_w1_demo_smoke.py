"""W1 Day 5 演示等价冒烟（Mock，替代部分人工 T5.4 检查）。"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPERAI_MOCK", "1")


def test_w1_list_plugins_ten() -> None:
    from src.harness.plugin_registry import list_plugins

    assert len(list_plugins()) == 10


def test_w1_invoke_u_returns_segments() -> None:
    from src.harness.plugin_registry import invoke

    ctx = {
        "task_id": str(uuid.uuid4()),
        "run_id": str(uuid.uuid4()),
        "pack_id": "media",
        "agent_id": "U",
        "raw_input": "demo",
        "upstream": {
            "D": {
                "insights": ["i"],
                "angles": ["a"],
                "risk_flags": [],
                "evidence_spans": [{"field": "raw_input", "snippet": "demo"}],
            }
        },
    }
    out = invoke("U", use_llm=False, context=ctx, llm_cfg={})
    assert "segments" in out


def test_w1_t01_pipeline_three_steps_in_db() -> None:
    """等价 Streamlit T-01：D/C/N 三步成功写入 run_steps。"""
    from src.orchestrator import execute_pipeline, load_config, open_connection
    from src.storage.db import query_all

    cfg = load_config(ROOT)
    conn = open_connection(ROOT, cfg)
    res = execute_pipeline(
        ROOT, conn, cfg,
        task_id=str(uuid.uuid4()),
        title="测试",
        brand_voice="克制",
        platforms=["weibo", "xhs"],
        raw_input="校园音乐节预热，强调安全与包容。",
    )
    assert res["ok"]
    steps = query_all(
        conn,
        "SELECT step, status FROM run_steps WHERE run_id = ? AND status = 'success' ORDER BY id",
        (res["run_id"],),
    )
    step_names = [str(r["step"]) for r in steps]
    assert step_names.count("D") >= 1
    assert step_names.count("C") >= 1
    assert step_names.count("N") >= 1
