"""D→C→N 编排：写 SQLite + JSONL，供 Streamlit 调用。"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Callable
from typing import Any

StepPhase = str  # "start" | "done" | "error"
OnStepCallback = Callable[[str, StepPhase], None]

import yaml

from src.agents.c_agent import run_c
from src.agents.d_agent import run_d
from src.agents.n_agent import run_n
from src.data_hub import extract_metrics, inject_metrics_context
from src.llm_runtime import (
    apply_llm_cfg,
    effective_short_output,
    effective_skip_review,
    effective_split_models,
    effective_use_llm,
    model_for_step,
)
from src.harness.dag_runner import run_dag
from src.harness.pack_loader import load_pack
from src.logutil import append_event
from src.storage.db import connect, execute, init_db, query_all


def load_config(root: Path) -> dict[str, Any]:
    cfg_path = root / "config.yaml"
    with cfg_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_paths(root: Path, cfg: dict[str, Any]) -> tuple[Path, Path]:
    sqlite_rel = cfg.get("paths", {}).get("sqlite", "data/operai.sqlite3")
    logs_rel = cfg.get("paths", {}).get("logs_dir", "data/logs")
    return (root / sqlite_rel).resolve(), (root / logs_rel).resolve()


def should_use_llm() -> bool:
    """兼容旧调用；优先走 llm_runtime 有效配置。"""
    return effective_use_llm()


def llm_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    lc = cfg.get("llm", {})
    max_tok = int(lc.get("max_tokens", 2048))
    base = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "temperature": float(lc.get("temperature", 0.4)),
        "max_tokens": max_tok,
        "timeout_seconds": float(lc.get("timeout_seconds", 90)),
        "max_retries": int(lc.get("max_retries", 1)),
    }
    return apply_llm_cfg(base)


def llm_settings_for_run(cfg: dict[str, Any]) -> dict[str, Any]:
    """含 short_output 缩短上限的运行时 LLM 配置。"""
    base = llm_settings(cfg)
    if effective_short_output(cfg):
        base["max_tokens"] = min(int(base["max_tokens"]), 900)
    return base


def llm_settings_for_step(cfg: dict[str, Any], step: str) -> dict[str, Any]:
    """按步骤选择模型（D 小 / C 大）或统一模型。"""
    base = llm_settings_for_run(cfg)
    if effective_split_models():
        base = dict(base)
        base["model"] = model_for_step(cfg, step)
    return base


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_pack_and_dag(
    root: Path,
    conn: sqlite3.Connection,
    *,
    task_id: str,
    cfg: dict[str, Any],
) -> tuple[str, list[str]]:
    harness = cfg.get("harness") or {}
    default_pack = str(harness.get("default_pack_id", "media"))
    rows = query_all(conn, "SELECT pack_id, dag_json FROM tasks WHERE id = ?", (task_id,))
    pack_id = default_pack
    dag: list[str] | None = None
    if rows:
        row = rows[0]
        keys = set(row.keys())
        if "pack_id" in keys and row["pack_id"]:
            pack_id = str(row["pack_id"])
        if "dag_json" in keys and row["dag_json"]:
            try:
                parsed = json.loads(row["dag_json"])
                if isinstance(parsed, list) and parsed:
                    dag = [str(x).strip().upper() for x in parsed]
            except json.JSONDecodeError:
                dag = None
    if dag is None:
        dag = list(load_pack(root, pack_id).default_dag)
    return pack_id, dag


def upsert_task(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    title: str,
    brand_voice: str,
    platforms: list[str],
    raw_input: str,
    pack_id: str = "media",
    dag_json: str | None = None,
) -> None:
    ts = _now()
    rows = query_all(conn, "SELECT id FROM tasks WHERE id = ?", (task_id,))
    if rows:
        execute(
            conn,
            "UPDATE tasks SET title=?, brand_voice=?, platforms_json=?, raw_input=?, pack_id=?, dag_json=?, updated_at=? WHERE id=?",
            (
                title,
                brand_voice,
                json.dumps(platforms, ensure_ascii=False),
                raw_input,
                pack_id,
                dag_json,
                ts,
                task_id,
            ),
        )
    else:
        execute(
            conn,
            "INSERT INTO tasks (id, title, brand_voice, platforms_json, raw_input, pack_id, dag_json, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                task_id,
                title,
                brand_voice,
                json.dumps(platforms, ensure_ascii=False),
                raw_input,
                pack_id,
                dag_json,
                ts,
                ts,
            ),
        )


def execute_pipeline(
    root: Path,
    conn: sqlite3.Connection,
    cfg: dict[str, Any],
    *,
    task_id: str,
    title: str,
    brand_voice: str,
    platforms: list[str],
    raw_input: str,
    on_step: OnStepCallback | None = None,
) -> dict[str, Any]:
    raw_input = (raw_input or "").strip()
    if not raw_input:
        return {"ok": False, "error": "请输入素材正文，或加载内置样例。"}

    _, logs_dir = resolve_paths(root, cfg)
    use_llm = should_use_llm()
    demo_mode = bool(cfg.get("demo_mode", {}).get("short_output"))
    skip_review = effective_skip_review(cfg)

    platforms_eff = platforms if platforms else ["weibo", "wechat", "xhs"]
    pack_id, dag = _resolve_pack_and_dag(root, conn, task_id=task_id, cfg=cfg)
    dag_json = json.dumps(dag, ensure_ascii=False)
    upsert_task(
        conn,
        task_id=task_id,
        title=title,
        brand_voice=brand_voice,
        platforms=platforms_eff,
        raw_input=raw_input,
        pack_id=pack_id,
        dag_json=dag_json,
    )

    run_id = str(uuid.uuid4())
    started = _now()
    execute(
        conn,
        "INSERT INTO runs (id, task_id, status, demo_mode, mock, error_message, started_at, finished_at, pack_id) VALUES (?,?,?,?,?,?,?,?,?)",
        (run_id, task_id, "running", int(demo_mode), int(not use_llm), None, started, None, pack_id),
    )

    append_event(
        logs_dir,
        run_id,
        {"event": "run_start", "task_id": task_id, "mock": not use_llm, "pack_id": pack_id, "dag": dag},
    )

    def _notify(step: str, phase: StepPhase) -> None:
        if on_step:
            on_step(step, phase)

    try:
        # 统一数据基座：每次 run 开始时提取结构化指标
        extract_metrics(raw_input, structured_metrics=None)

        payloads = run_dag(
            dag,
            task_id=task_id,
            run_id=run_id,
            pack_id=pack_id,
            brand_voice=brand_voice,
            platforms=platforms_eff,
            raw_input=raw_input,
            structured_metrics=None,
            use_llm=use_llm,
            root=root,
            conn=conn,
            logs_dir=logs_dir,
            run_step=_run_step,
            llm_cfg_for_step=lambda step: llm_settings_for_step(cfg, step),
            on_step=on_step,
        )
        d_out = payloads.get("D") or {}
        c_out = payloads.get("C") or {}
        n_out = payloads.get("N") or {}

        # 构建完整的 Agent 输出包
        agent_outputs = dict(payloads)
        bundle = {
            "d_agent": d_out,
            "c_agent": c_out,
            "n_agent": n_out,
            "agent_outputs": agent_outputs,
        }
        execute(
            conn,
            "INSERT OR REPLACE INTO artifacts (run_id, drafts_json, drafts_final_json) VALUES (?,?,?)",
            (run_id, json.dumps(bundle, ensure_ascii=False), json.dumps(bundle, ensure_ascii=False)),
        )

        final_status = "success" if skip_review else "need_review"
        execute(
            conn,
            "UPDATE runs SET status=?, finished_at=? WHERE id=?",
            (final_status, _now(), run_id),
        )
        append_event(logs_dir, run_id, {"event": "run_end", "status": final_status})
        return {
            "ok": True,
            "run_id": run_id,
            "status": final_status,
            "use_llm": use_llm,
            "d_out": d_out,
            "c_out": c_out,
            "n_out": n_out,
            "agent_outputs": agent_outputs,
            "pack_id": pack_id,
            "dag": dag,
        }
    except Exception as e:  # noqa: BLE001
        _notify("pipeline", "error")
        execute(
            conn,
            "UPDATE runs SET status=?, finished_at=?, error_message=? WHERE id=?",
            ("failed", _now(), str(e)[:2000], run_id),
        )
        append_event(logs_dir, run_id, {"event": "run_fail", "error": str(e)})
        return {"ok": False, "error": str(e), "run_id": run_id}


def open_connection(root: Path, cfg: dict[str, Any]) -> sqlite3.Connection:
    db_path, _ = resolve_paths(root, cfg)
    conn = connect(db_path)
    init_db(conn)
    return conn


def confirm_review(conn: sqlite3.Connection, run_id: str) -> None:
    ts = _now()
    execute(conn, "UPDATE runs SET status=?, finished_at=? WHERE id=?", ("success", ts, run_id))


def _run_step(
    conn: sqlite3.Connection,
    logs_dir: Path,
    run_id: str,
    name: str,
    fn: Any,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO run_steps (run_id, step, status, input_summary, output_summary, duration_ms, raw_json) VALUES (?,?,?,?,?,?,?)",
        (run_id, name, "running", None, None, None, None),
    )
    step_row_id = int(cur.lastrowid)
    conn.commit()
    try:
        out = fn()
        usage = out.pop("_llm_usage", None) if isinstance(out, dict) else None
        ms = int((time.perf_counter() - t0) * 1000)
        raw = json.dumps(out, ensure_ascii=False)
        summary = raw[:2000]
        char_est = len(raw)
        execute(
            conn,
            "UPDATE run_steps SET status=?, output_summary=?, duration_ms=?, raw_json=? WHERE id=?",
            ("success", summary, ms, raw, step_row_id),
        )
        ev: dict[str, Any] = {
            "event": "step_ok",
            "step": name,
            "duration_ms": ms,
            "output_chars": char_est,
        }
        if usage:
            ev["llm_usage"] = usage
        append_event(logs_dir, run_id, ev)
        return out
    except Exception as e:  # noqa: BLE001
        ms = int((time.perf_counter() - t0) * 1000)
        err = str(e)
        execute(
            conn,
            "UPDATE run_steps SET status=?, output_summary=?, duration_ms=? WHERE id=?",
            ("failed", err[:2000], ms, step_row_id),
        )
        append_event(logs_dir, run_id, {"event": "step_fail", "step": name, "error": err})
        raise


def rerun_agent_step(
    root: Path,
    conn: sqlite3.Connection,
    cfg: dict[str, Any],
    *,
    run_id: str,
    step: str,
) -> dict[str, Any]:
    """单步重跑 D / C / N；保留未重跑步骤的既有输出。"""
    step = step.upper()
    if step not in ("D", "C", "N"):
        return {"ok": False, "error": f"不支持的重跑步骤：{step}"}

    # 内联 DB 查询（tasks.py 已删除）
    run_rows = query_all(conn, "SELECT task_id, status FROM runs WHERE id = ?", (run_id,))
    if not run_rows:
        return {"ok": False, "error": "run 不存在"}
    task_id = str(run_rows[0]["task_id"])

    task_rows = query_all(conn, "SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not task_rows:
        return {"ok": False, "error": "关联任务不存在"}
    task = task_rows[0]

    # 从 run_steps 还原 bundle
    step_rows = query_all(conn, "SELECT step, raw_json FROM run_steps WHERE run_id=? AND status='success' ORDER BY id", (run_id,))
    bundle: dict[str, Any] = {"d_out": {}, "c_out": {}, "n_out": {}}
    for r in step_rows:
        if r["step"] == "D": bundle["d_out"] = json.loads(r["raw_json"])
        elif r["step"] == "C": bundle["c_out"] = json.loads(r["raw_json"])
        elif r["step"] == "N": bundle["n_out"] = json.loads(r["raw_json"])
    if not (bundle.get("d_out") and bundle.get("c_out") and bundle.get("n_out")):
        return {"ok": False, "error": "无法加载该 run 的历史输出，请先完整运行"}

    _, logs_dir = resolve_paths(root, cfg)
    use_llm = should_use_llm()
    raw_input = str(task["raw_input"] or "").strip()
    brand_voice = str(task["brand_voice"] or "")
    platforms_eff = json.loads(task["platforms_json"] or "[]") or ["weibo", "wechat", "xhs"]

    d_out = dict(bundle["d_out"])
    c_out = dict(bundle["c_out"])
    n_out = dict(bundle["n_out"])

    append_event(logs_dir, run_id, {"event": "step_rerun_start", "step": step})

    try:
        if step == "D":
            d_out = _run_step(
                conn,
                logs_dir,
                run_id,
                "D",
                lambda: run_d(
                    use_llm=use_llm,
                    raw_input=raw_input,
                    brand_voice=brand_voice,
                    llm_cfg=llm_settings_for_step(cfg, "D"),
                ),
            )
        elif step == "C":
            c_out = _run_step(
                conn,
                logs_dir,
                run_id,
                "C",
                lambda: run_c(
                    use_llm=use_llm,
                    d_out=d_out,
                    platforms=platforms_eff,
                    llm_cfg=llm_settings_for_step(cfg, "C"),
                    root=root,
                ),
            )
        else:
            n_out = _run_step(
                conn,
                logs_dir,
                run_id,
                "N",
                lambda: run_n(
                    use_llm=use_llm,
                    c_out=c_out,
                    llm_cfg=llm_settings_for_step(cfg, "N"),
                    platforms=platforms_eff,
                    root=root,
                ),
            )

        merged = {"d_agent": d_out, "c_agent": c_out, "n_agent": n_out}
        execute(
            conn,
            "INSERT OR REPLACE INTO artifacts (run_id, drafts_json, drafts_final_json) VALUES (?,?,?)",
            (run_id, json.dumps(merged, ensure_ascii=False), json.dumps(merged, ensure_ascii=False)),
        )
        execute(conn, "UPDATE runs SET status=? WHERE id=?", ("need_review", run_id))
        append_event(logs_dir, run_id, {"event": "step_rerun_end", "step": step, "status": "need_review"})

        stale: list[str] = []
        if step == "D":
            stale = ["C", "N"]
        elif step == "C":
            stale = ["N"]

        return {
            "ok": True,
            "run_id": run_id,
            "status": "need_review",
            "use_llm": use_llm,
            "d_out": d_out,
            "c_out": c_out,
            "n_out": n_out,
            "rerun_step": step,
            "stale_steps": stale,
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "run_id": run_id}


def rerun_downstream(
    root: Path,
    conn: sqlite3.Connection,
    cfg: dict[str, Any],
    *,
    run_id: str,
    after_step: str,
) -> dict[str, Any]:
    """重跑下游：D 之后同步 C+N；C 之后同步 N。"""
    after_step = after_step.upper()
    chain = {"D": ["C", "N"], "C": ["N"]}
    steps = chain.get(after_step)
    if not steps:
        return {"ok": False, "error": f"不支持从 {after_step} 同步下游"}

    last: dict[str, Any] = {"ok": False, "error": "未执行"}
    for step in steps:
        last = rerun_agent_step(root, conn, cfg, run_id=run_id, step=step)
        if not last.get("ok"):
            last["error"] = f"同步 {step} 失败：{last.get('error', '')}"
            return last
    last["rerun_step"] = after_step
    last["stale_steps"] = []
    last["downstream_sync"] = steps
    return last
