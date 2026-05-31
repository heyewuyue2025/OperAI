"""Harness DAG 执行：按序 invoke 插件并注入 upstream（全部前序输出）。"""
from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.agents.base import HarnessContext
from src.data_hub import inject_metrics_context
from src.harness.plugin_registry import invoke

OnStepCallback = Callable[[str, str], None]
RunStepFn = Callable[
    [sqlite3.Connection, Path, str, str, Callable[[], dict[str, Any]]],
    dict[str, Any],
]
LlmCfgForStep = Callable[[str], dict[str, Any]]


def build_upstream(agent_id: str, results: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """返回当前 Agent 之前所有步骤的输出作为 upstream（排除自身）。

    每个 Agent 自由选择上游中的相关字段，Harness 不做裁剪。
    """
    return {k: v for k, v in results.items() if k.upper() != agent_id.upper()}


def run_dag(
    dag: list[str],
    *,
    task_id: str,
    run_id: str,
    pack_id: str,
    brand_voice: str,
    platforms: list[str],
    raw_input: str,
    structured_metrics: dict[str, Any] | None,
    use_llm: bool,
    root: Path,
    conn: sqlite3.Connection,
    logs_dir: Path,
    run_step: RunStepFn,
    llm_cfg_for_step: LlmCfgForStep,
    on_step: OnStepCallback | None = None,
) -> dict[str, dict[str, Any]]:
    """执行 DAG，返回 {agent_id: payload}。"""
    results: dict[str, dict[str, Any]] = {}
    metrics = structured_metrics or {}

    for agent_id in dag:
        aid = str(agent_id).strip().upper()
        if on_step:
            on_step(aid, "start")

        upstream = build_upstream(aid, results)
        ctx: HarnessContext = {
            "task_id": task_id,
            "run_id": run_id,
            "pack_id": pack_id,
            "agent_id": aid,
            "brand_voice": brand_voice,
            "platforms": platforms,
            "raw_input": raw_input,
            "structured_metrics": metrics,
            "upstream": upstream,
        }
        # 注入统一数据基座的指标
        ctx = inject_metrics_context(ctx)
        llm_cfg = llm_cfg_for_step(aid)

        def _invoke() -> dict[str, Any]:
            return invoke(aid, use_llm=use_llm, context=ctx, llm_cfg=llm_cfg, root=root)

        out = run_step(conn, logs_dir, run_id, aid, _invoke)
        results[aid] = out

        # Agent 输出验证（非 LLM 规则检查）
        _validate_agent_output(conn, run_id, aid, out, ctx, root)

        if on_step:
            on_step(aid, "done")

    return results


def _validate_agent_output(
    conn, run_id: str, agent_id: str, payload: dict[str, Any],
    context: dict[str, Any], root: Path,
) -> None:
    """调用 Agent 的 validate() 函数，将问题写入 run_steps 的备注。"""
    from importlib import import_module
    agent_module_name = f"src.agents.{agent_id.lower()}_agent"
    try:
        module = import_module(agent_module_name)
        validate_fn = getattr(module, "validate", None)
        if validate_fn is None:
            return
        issues = validate_fn(payload)
        if issues:
            import json
            conn.execute(
                "UPDATE run_steps SET output_summary = output_summary || ? WHERE run_id=? AND step=? AND status='success'",
                (f"\n[validate] {len(issues)} issue(s): " + "; ".join(issues[:5]), run_id, agent_id),
            )
            conn.commit()
    except Exception:
        pass  # validate 失败不阻塞主流程
