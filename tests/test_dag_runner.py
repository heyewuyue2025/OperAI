"""DAG runner：upstream 注入与 invoke 串联。"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPERAI_MOCK", "1")


def test_build_upstream_dcn() -> None:
    from src.harness.dag_runner import build_upstream

    # D 最先执行，此时 results 为空
    assert build_upstream("D", {}) == {}

    # C 在 D 之后执行
    after_d = {"D": {"insights": ["a"]}}
    assert build_upstream("C", after_d)["D"]["insights"] == ["a"]

    # N 在 D、C 之后执行（也可能有 U）
    after_dc = {"D": {"insights": ["a"]}, "C": {"drafts": {"weibo": "x"}}}
    assert build_upstream("N", after_dc)["C"]["drafts"]["weibo"] == "x"
    assert build_upstream("N", after_dc)["D"]["insights"] == ["a"]


def test_run_dag_mock_dcn() -> None:
    from src.harness.dag_runner import run_dag
    from src.orchestrator import _run_step, load_config, open_connection, resolve_paths

    cfg = load_config(ROOT)
    conn = open_connection(ROOT, cfg)
    _, logs_dir = resolve_paths(ROOT, cfg)
    run_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())

    payloads = run_dag(
        ["D", "C", "N"],
        task_id=task_id,
        run_id=run_id,
        pack_id="media",
        brand_voice="克制",
        platforms=["weibo", "xhs"],
        raw_input="DAG 单测素材，校园音乐节。",
        structured_metrics=None,
        use_llm=False,
        root=ROOT,
        conn=conn,
        logs_dir=logs_dir,
        run_step=_run_step,
        llm_cfg_for_step=lambda _s: {},
    )
    assert set(payloads.keys()) == {"D", "C", "N"}
    assert payloads["D"].get("insights")
    assert payloads["C"].get("drafts")
    assert payloads["N"].get("schedule_suggestions")
