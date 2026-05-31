from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from src.storage.db import init_db


@pytest.fixture
def conn_with_archive_rows(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    conn.execute(
        "INSERT INTO tasks (id, title, brand_voice, platforms_json, raw_input, pack_id, dag_json, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "task-1",
            "新品发布",
            "克制可信",
            json.dumps(["weibo", "wechat"], ensure_ascii=False),
            "原始素材包含 36 小时续航和 35dB 降噪。",
            "media",
            json.dumps(["D", "C"], ensure_ascii=False),
            "2026-05-31T10:00:00+00:00",
            "2026-05-31T10:00:00+00:00",
        ),
    )
    conn.execute(
        "INSERT INTO runs (id, task_id, status, demo_mode, mock, error_message, started_at, finished_at, pack_id) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "run-1",
            "task-1",
            "success",
            0,
            1,
            None,
            "2026-05-31T10:01:00+00:00",
            "2026-05-31T10:01:03+00:00",
            "media",
        ),
    )
    d_out = {"insights": ["洞察"], "_metrics": {"numbers": ["36", "35"]}}
    c_out = {"drafts": {"weibo": "微博文案"}}
    for step, raw in (("D", d_out), ("C", c_out)):
        conn.execute(
            "INSERT INTO run_steps (run_id, step, status, input_summary, output_summary, duration_ms, raw_json) "
            "VALUES (?,?,?,?,?,?,?)",
            ("run-1", step, "success", None, json.dumps(raw, ensure_ascii=False), 10, json.dumps(raw, ensure_ascii=False)),
        )
    bundle = {"agent_outputs": {"D": d_out, "C": c_out}}
    conn.execute(
        "INSERT INTO artifacts (run_id, drafts_json, drafts_final_json) VALUES (?,?,?)",
        ("run-1", json.dumps(bundle, ensure_ascii=False), json.dumps(bundle, ensure_ascii=False)),
    )
    conn.commit()
    (tmp_path / "run-1.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"event": "run_start", "run_id": "run-1"}, ensure_ascii=False),
                json.dumps({"event": "step_ok", "step": "D"}, ensure_ascii=False),
            ]
        ),
        encoding="utf-8",
    )
    return conn


def test_list_agent_files_contains_ten_agents() -> None:
    from src.archive_view import list_agent_files

    agents = list_agent_files()

    assert len(agents) == 10
    assert agents["D"]["title"] == "数据运营"
    assert agents["C"]["archive_role"]


def test_load_run_dossier_returns_steps_and_artifacts(tmp_path: Path, conn_with_archive_rows: sqlite3.Connection) -> None:
    from src.archive_view import load_run_dossier

    dossier = load_run_dossier(conn_with_archive_rows, tmp_path, "run-1")

    assert dossier["run_id"] == "run-1"
    assert dossier["status"] == "success"
    assert [s["step"] for s in dossier["steps"]] == ["D", "C"]
    assert dossier["agent_outputs"]["D"]["insights"] == ["洞察"]


def test_build_evidence_chain_extracts_metrics_and_trace(
    tmp_path: Path, conn_with_archive_rows: sqlite3.Connection
) -> None:
    from src.archive_view import build_evidence_chain

    chain = build_evidence_chain(conn_with_archive_rows, tmp_path, "run-1")

    assert chain["trace_events"][0]["event"] == "run_start"
    assert chain["nodes"][0]["label"] == "Raw Input"
    assert chain["nodes"][-1]["label"] == "Export Readiness"


def test_build_archive_summary_counts_runs(tmp_path: Path, conn_with_archive_rows: sqlite3.Connection) -> None:
    from src.archive_view import build_archive_summary

    summary = build_archive_summary(conn_with_archive_rows, tmp_path)

    assert summary["agent_count"] == 10
    assert summary["run_count"] == 1
    assert summary["latest_run"]["id"] == "run-1"
