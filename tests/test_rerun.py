from __future__ import annotations

import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPERAI_MOCK", "1")


def test_rerun_agent_step_n() -> None:
    from src.orchestrator import execute_pipeline, load_config, open_connection, rerun_agent_step

    cfg = load_config(ROOT)
    conn = open_connection(ROOT, cfg)
    tid = str(uuid.uuid4())
    res = execute_pipeline(
        ROOT,
        conn,
        cfg,
        task_id=tid,
        title="rerun-test",
        brand_voice="",
        platforms=["weibo"],
        raw_input="测试素材用于重跑 N。",
    )
    assert res["ok"]
    rid = res["run_id"]
    rr = rerun_agent_step(ROOT, conn, cfg, run_id=rid, step="N")
    assert rr["ok"] is True
    assert rr["n_out"].get("hashtags")
