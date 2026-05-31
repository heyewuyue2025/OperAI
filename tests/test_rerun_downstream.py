from __future__ import annotations

import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPERAI_MOCK", "1")


def test_rerun_downstream_after_d() -> None:
    from src.orchestrator import execute_pipeline, load_config, open_connection, rerun_downstream

    cfg = load_config(ROOT)
    conn = open_connection(ROOT, cfg)
    tid = str(uuid.uuid4())
    res = execute_pipeline(
        ROOT,
        conn,
        cfg,
        task_id=tid,
        title="ds",
        brand_voice="",
        platforms=["weibo", "xhs"],
        raw_input="下游同步测试素材。",
    )
    assert res["ok"]
    rr = rerun_downstream(ROOT, conn, cfg, run_id=res["run_id"], after_step="D")
    assert rr["ok"] is True
    assert rr.get("downstream_sync") == ["C", "N"]
    assert rr.get("stale_steps") == []
