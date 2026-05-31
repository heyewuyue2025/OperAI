"""编排冒烟测试：强制 Mock，不调用外网。"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPERAI_MOCK", "1")


def test_execute_pipeline_mock_ok() -> None:
    from src.orchestrator import execute_pipeline, load_config, open_connection

    cfg = load_config(ROOT)
    conn = open_connection(ROOT, cfg)
    tid = str(uuid.uuid4())
    res = execute_pipeline(
        ROOT,
        conn,
        cfg,
        task_id=tid,
        title="pytest",
        brand_voice="克制",
        platforms=["weibo", "xhs"],
        raw_input="校园音乐节预热，强调安全与包容。",
    )
    assert res["ok"] is True
    assert res["status"] in ("need_review", "success")
    assert res["use_llm"] is False
    assert "drafts" in res["c_out"]
    assert "weibo" in res["c_out"]["drafts"]


def test_execute_pipeline_on_step_callback() -> None:
    from src.orchestrator import execute_pipeline, load_config, open_connection

    cfg = load_config(ROOT)
    conn = open_connection(ROOT, cfg)
    events: list[tuple[str, str]] = []

    def on_step(step: str, phase: str) -> None:
        events.append((step, phase))

    res = execute_pipeline(
        ROOT,
        conn,
        cfg,
        task_id=str(uuid.uuid4()),
        title="cb",
        brand_voice="",
        platforms=["weibo"],
        raw_input="回调测试素材。",
        on_step=on_step,
    )
    assert res["ok"]
    assert ("D", "start") in events and ("D", "done") in events
    assert ("C", "start") in events and ("N", "done") in events


def test_execute_pipeline_empty_input() -> None:
    from src.orchestrator import execute_pipeline, load_config, open_connection

    cfg = load_config(ROOT)
    conn = open_connection(ROOT, cfg)
    res = execute_pipeline(
        ROOT,
        conn,
        cfg,
        task_id=str(uuid.uuid4()),
        title="x",
        brand_voice="",
        platforms=["weibo"],
        raw_input="   ",
    )
    assert res["ok"] is False
    assert "error" in res
