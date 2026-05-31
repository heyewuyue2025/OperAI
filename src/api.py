"""OperAI Enterprise API — FastAPI REST 接口。

企业接入方式:
  POST /api/v1/runs             创建并执行 DAG 运行
  GET  /api/v1/runs/{run_id}    查询运行状态与结果
  GET  /api/v1/runs/{run_id}/trace  查询步骤轨迹
  POST /api/v1/runs/{run_id}/export  导出战役包
  GET  /api/v1/agents            列出 Agent 插件
  GET  /api/v1/packs             列出行业 Pack

认证: X-OperAI-API-Key 请求头
多租户: X-OperAI-Tenant 请求头（可选，缺省 default）
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from src.export_campaign import build_campaign_markdown
from src.harness.pack_loader import list_packs, load_pack
from src.harness.plugin_registry import list_plugins
from src.orchestrator import execute_pipeline, load_config, open_connection
from src.storage.db import query_all

ROOT = Path(__file__).resolve().parents[1]

app = FastAPI(title="OperAI Enterprise API", version="1.0.0")
_cfg = load_config(ROOT)
_conn = open_connection(ROOT, _cfg)

# ── Models ──


class RunRequest(BaseModel):
    task_id: str | None = Field(default=None, description="复用已有任务 ID，不传则新建")
    title: str = Field(default="API Run", max_length=200)
    pack_id: str = Field(default="media", description="行业 Pack ID")
    brand_voice: str = Field(default="")
    platforms: list[str] = Field(default=["weibo", "wechat", "xhs"])
    raw_input: str = Field(..., min_length=1, description="素材正文")
    webhook_url: str | None = Field(default=None, description="完成后的回调 URL")


class RunResponse(BaseModel):
    ok: bool
    run_id: str
    status: str
    pack_id: str
    dag: list[str]
    agent_outputs: dict[str, dict[str, Any]] | None = None
    error: str | None = None


class AgentInfo(BaseModel):
    agent_id: str
    version: str
    description: str
    status: str
    tier: str


class PackInfo(BaseModel):
    id: str
    name: str
    description: str
    default_dag: list[str]


# ── Helpers ──




# 简单的 API Key 存储（生产环境替换为数据库/外部服务）
import os as _os
_VALID_KEYS: set[str] = set()
_env_key = _os.getenv("OPERAI_API_KEY", "").strip()
if _env_key:
    _VALID_KEYS.add(_env_key)

# 开发模式：任意 Key 或空 Key 均可访问
_DEV_MODE = not bool(_env_key)


def _check_auth(request: Request) -> str | None:
    """验证 API Key。开发模式放行；生产模式校验。返回 tenant_id。"""
    if _DEV_MODE:
        return request.headers.get("X-OperAI-Tenant", "default")
    api_key = request.headers.get("X-OperAI-API-Key", "")
    if not api_key or api_key not in _VALID_KEYS:
        raise HTTPException(401, "无效的 API Key")
    return request.headers.get("X-OperAI-Tenant", "default")


def configure_api_keys(*keys: str) -> None:
    """运行时配置 API Key（可从环境或配置加载）。"""
    global _DEV_MODE
    for k in keys:
        k = k.strip()
        if k:
            _VALID_KEYS.add(k)
    _DEV_MODE = len(_VALID_KEYS) == 0


# ── Endpoints ──


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/v1/agents", response_model=list[AgentInfo])
def list_agents_api(request: Request):
    _check_auth(request)
    tier_map = {"D": "rule_first", "N": "rule_first",
                 "U": "llm_augmented", "C": "llm_augmented", "A": "llm_augmented", "F": "llm_augmented",
                 "M": "strategy_advisory", "P": "strategy_advisory", "S": "strategy_advisory", "E": "strategy_advisory"}
    return [
        AgentInfo(agent_id=p.agent_id, version=p.version, description=p.description, status=p.status,
                  tier=tier_map.get(p.agent_id, "strategy_advisory"))
        for p in list_plugins()
    ]


@app.get("/api/v1/packs", response_model=list[PackInfo])
def list_packs_api(request: Request):
    _check_auth(request)
    return [
        PackInfo(id=p.id, name=p.name, description=p.description, default_dag=p.default_dag)
        for p in list_packs(ROOT)
    ]


@app.post("/api/v1/runs", response_model=RunResponse)
def create_run(body: RunRequest, request: Request, background_tasks: BackgroundTasks):
    _check_auth(request)

    raw_input = body.raw_input.strip()
    if not raw_input:
        raise HTTPException(400, "raw_input 不能为空")

    task_id = body.task_id or str(uuid.uuid4())

    result = execute_pipeline(
        ROOT, _conn, _cfg,
        task_id=task_id,
        title=body.title,
        brand_voice=body.brand_voice,
        platforms=body.platforms,
        raw_input=raw_input,
    )

    resp = RunResponse(
        ok=result.get("ok", False),
        run_id=result.get("run_id", ""),
        status=result.get("status", "failed"),
        pack_id=result.get("pack_id", body.pack_id),
        dag=result.get("dag", []),
        agent_outputs=result.get("agent_outputs") if result.get("ok") else None,
        error=result.get("error"),
    )

    # Webhook 回调（异步）
    if body.webhook_url and result.get("ok"):
        background_tasks.add_task(_fire_webhook, body.webhook_url, resp.model_dump())

    return resp


@app.get("/api/v1/runs/{run_id}")
def get_run(run_id: str, request: Request):
    _check_auth(request)
    rows = query_all(_conn, "SELECT * FROM runs WHERE id = ?", (run_id,))
    if not rows:
        raise HTTPException(404, "run 不存在")
    row = rows[0]
    steps = query_all(_conn, "SELECT step, status, duration_ms, output_summary FROM run_steps WHERE run_id=? ORDER BY id", (run_id,))
    return {
        "run_id": run_id,
        "task_id": row["task_id"],
        "status": row["status"],
        "pack_id": row["pack_id"] if "pack_id" in row.keys() else "",
        "mock": bool(row["mock"]),
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "error_message": row["error_message"],
        "steps": [dict(s) for s in steps],
    }


@app.get("/api/v1/runs/{run_id}/trace")
def get_run_trace(run_id: str, request: Request):
    _check_auth(request)
    log_path = ROOT / _cfg["paths"]["logs_dir"] / f"{run_id}.jsonl"
    if not log_path.is_file():
        raise HTTPException(404, "日志文件不存在")
    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    return {"run_id": run_id, "events": [json.loads(line) for line in lines if line.strip()]}


@app.post("/api/v1/runs/{run_id}/export")
def export_run(run_id: str, request: Request, format: str = "markdown"):
    _check_auth(request)
    rows = query_all(_conn, "SELECT * FROM runs WHERE id = ?", (run_id,))
    if not rows:
        raise HTTPException(404, "run 不存在")
    row = rows[0]

    # 加载 Agent 输出
    artifacts = query_all(_conn, "SELECT drafts_json, drafts_final_json FROM artifacts WHERE run_id=?", (run_id,))
    agent_outputs: dict[str, Any] = {}
    if artifacts:
        blob = json.loads(artifacts[0]["drafts_final_json"] or artifacts[0]["drafts_json"] or "{}")
        agent_outputs = blob.get("agent_outputs") or {}

    task_rows = query_all(_conn, "SELECT title, pack_id, dag_json FROM tasks WHERE id=?", (row["task_id"],))
    title = str(task_rows[0]["title"]) if task_rows else "未命名"
    pack_id = str(task_rows[0]["pack_id"]) if task_rows and task_rows[0].get("pack_id") else "media"
    dag = json.loads(task_rows[0]["dag_json"]) if task_rows and task_rows[0].get("dag_json") else ["D", "C", "N"]

    md = build_campaign_markdown(
        title=title, task_id=row["task_id"], run_id=run_id,
        pack_id=pack_id, dag=dag, agent_outputs=agent_outputs,
    )
    return PlainTextResponse(content=md, media_type="text/markdown; charset=utf-8")


def _fire_webhook(url: str, payload: dict) -> None:
    """异步 Webhook 通知（FastAPI BackgroundTasks）。"""
    try:
        import urllib.request
        data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=8)
    except Exception:
        pass  # webhook 失败不阻塞


# ── 数据基座 ──

@app.get("/api/v1/data/metrics")
def get_data_metrics(request: Request):
    """获取 D-Agent 数据基座的当前指标缓存。"""
    _check_auth(request)
    from src.data_hub import get_cached
    snap = get_cached()
    if snap is None:
        return {"status": "empty", "message": "暂无数据，请先提交一次 run"}
    return {
        "status": "ok",
        "numbers": snap.numbers,
        "amounts": snap.amounts,
        "dates": snap.dates,
        "entities": snap.entities,
        "platforms": snap.platforms,
        "summary": snap.summary,
    }


# ── 健康检查 / 监控 ──

@app.get("/api/v1/stats")
def stats(request: Request):
    _check_auth(request)
    total_runs = query_all(_conn, "SELECT COUNT(*) AS c FROM runs", ())
    recent = query_all(_conn, "SELECT id, status, started_at FROM runs ORDER BY datetime(started_at) DESC LIMIT 10", ())
    return {
        "total_runs": int(total_runs[0]["c"]) if total_runs else 0,
        "recent": [dict(r) for r in recent],
        "agents": len(list_plugins()),
        "packs": len(list_packs(ROOT)),
    }
