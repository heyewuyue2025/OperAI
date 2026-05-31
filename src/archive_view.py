"""Archive OS view helpers.

This module keeps Streamlit/UI code away from raw SQL shape details. It returns
small dictionaries that map existing tasks, runs, steps, artifacts, and JSONL
logs into the Archive OS product model.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from src.harness.plugin_registry import list_plugins
from src.storage.db import query_all


AGENT_ARCHIVE_META: dict[str, dict[str, str]] = {
    "D": {"title": "数据运营", "archive_role": "把原始素材转为可验证指标、洞察和风险信号。", "tier": "Data Foundation"},
    "U": {"title": "用户运营", "archive_role": "把用户行为与生命周期整理成分群档案。", "tier": "LLM Augmented"},
    "C": {"title": "内容运营", "archive_role": "把洞察转换成多平台内容草案与合规注记。", "tier": "LLM Augmented"},
    "A": {"title": "活动运营", "archive_role": "把目标、预算与节奏整理成战役结构。", "tier": "LLM Augmented"},
    "N": {"title": "渠道运营", "archive_role": "把内容草案转为平台排期、标签和首评策略。", "tier": "Rule First"},
    "F": {"title": "流量运营", "archive_role": "把渠道表现转为评分和预算分配建议。", "tier": "LLM Augmented"},
    "M": {"title": "市场运营", "archive_role": "把品牌、竞品与趋势整理成市场判断。", "tier": "Strategy Advisory"},
    "P": {"title": "产品运营", "archive_role": "把反馈与功能信号转为迭代优先级。", "tier": "Strategy Advisory"},
    "S": {"title": "社群运营", "archive_role": "把互动语境转为社群动作、话术和 KOL 线索。", "tier": "Strategy Advisory"},
    "E": {"title": "交易运营", "archive_role": "把转化漏斗转为促销、CTA 和 GMV 动作。", "tier": "Strategy Advisory"},
}


def list_agent_files() -> dict[str, dict[str, str]]:
    """Return ten Agent records formatted as archive index entries."""
    plugins = {p.agent_id: p for p in list_plugins()}
    files: dict[str, dict[str, str]] = {}
    for aid, meta in AGENT_ARCHIVE_META.items():
        plugin = plugins.get(aid)
        files[aid] = {
            "agent_id": aid,
            "title": meta["title"],
            "archive_role": meta["archive_role"],
            "tier": meta["tier"],
            "status": plugin.status if plugin else "missing",
            "description": plugin.description if plugin else "",
            "version": plugin.version if plugin else "",
        }
    return files


def _json_loads(value: Any, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return default


def load_trace_events(logs_dir: Path, run_id: str, limit: int = 80) -> list[dict[str, Any]]:
    """Load the tail of a run JSONL trace without failing on malformed lines."""
    log_path = logs_dir / f"{run_id}.jsonl"
    if not log_path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({"event": "unparsed", "raw": line[:500]})
    return events[-limit:]


def _bundle_agent_outputs(bundle: dict[str, Any]) -> dict[str, Any]:
    if isinstance(bundle.get("agent_outputs"), dict):
        return bundle["agent_outputs"]
    outputs: dict[str, Any] = {}
    legacy_map = {"D": "d_agent", "C": "c_agent", "N": "n_agent"}
    for aid, key in legacy_map.items():
        if isinstance(bundle.get(key), dict):
            outputs[aid] = bundle[key]
    return outputs


def load_run_dossier(conn: sqlite3.Connection, logs_dir: Path, run_id: str) -> dict[str, Any]:
    """Return one run as a UI-ready dossier."""
    runs = query_all(conn, "SELECT * FROM runs WHERE id=?", (run_id,))
    if not runs:
        return {}
    run = runs[0]
    steps = [
        dict(row)
        for row in query_all(
            conn,
            "SELECT step, status, duration_ms, output_summary, raw_json FROM run_steps WHERE run_id=? ORDER BY id",
            (run_id,),
        )
    ]
    artifacts = query_all(conn, "SELECT drafts_final_json, drafts_json FROM artifacts WHERE run_id=?", (run_id,))
    bundle: dict[str, Any] = {}
    if artifacts:
        bundle = _json_loads(artifacts[0]["drafts_final_json"] or artifacts[0]["drafts_json"], {})
    keys = set(run.keys())
    return {
        "run_id": run_id,
        "task_id": run["task_id"],
        "status": run["status"],
        "mock": bool(run["mock"]),
        "pack_id": run["pack_id"] if "pack_id" in keys else "media",
        "started_at": run["started_at"],
        "finished_at": run["finished_at"],
        "error_message": run["error_message"],
        "steps": steps,
        "agent_outputs": _bundle_agent_outputs(bundle),
        "trace_events": load_trace_events(logs_dir, run_id),
    }


def build_evidence_chain(conn: sqlite3.Connection, logs_dir: Path, run_id: str) -> dict[str, Any]:
    """Build a compact proof chain for a run dossier."""
    dossier = load_run_dossier(conn, logs_dir, run_id)
    outputs = dossier.get("agent_outputs") or {}
    d_out = outputs.get("D") or {}
    c_out = outputs.get("C") or {}
    n_out = outputs.get("N") or {}
    nodes = [
        {"label": "Raw Input", "status": "captured"},
        {"label": "Metrics", "status": "ready" if d_out.get("_metrics") else "implicit"},
        {"label": "D Insight", "status": "ready" if d_out else "missing"},
        {"label": "C Draft", "status": "ready" if c_out else "missing"},
        {"label": "N Schedule", "status": "ready" if n_out else "missing"},
        {"label": "Export Readiness", "status": "ready" if dossier.get("status") in {"success", "need_review"} else "blocked"},
    ]
    return {"run_id": run_id, "nodes": nodes, "trace_events": dossier.get("trace_events", [])}


def build_archive_summary(conn: sqlite3.Connection, logs_dir: Path) -> dict[str, Any]:
    """Return high-level archive counters for sidebar/header surfaces."""
    run_count = query_all(conn, "SELECT COUNT(*) AS c FROM runs", ())
    task_count = query_all(conn, "SELECT COUNT(*) AS c FROM tasks", ())
    latest = query_all(conn, "SELECT id, task_id, status, started_at FROM runs ORDER BY datetime(started_at) DESC LIMIT 1", ())
    return {
        "agent_count": len(list_agent_files()),
        "task_count": int(task_count[0]["c"]) if task_count else 0,
        "run_count": int(run_count[0]["c"]) if run_count else 0,
        "log_count": len(list(logs_dir.glob("*.jsonl"))) if logs_dir.exists() else 0,
        "latest_run": dict(latest[0]) if latest else None,
    }
