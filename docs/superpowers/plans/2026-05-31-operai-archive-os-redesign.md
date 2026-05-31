# OperAI Archive OS Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild OperAI into Archive OS: a research archive interface for task files, Agent index, run dossiers, evidence chains, and export vaults.

**Architecture:** Keep the existing Python/Streamlit/FastAPI/SQLite stack and add a thin archive view layer for UI-friendly data. Rebuild the static frontend with shared HTML/CSS/JS patterns, then restructure Streamlit around the Archive Desk model while preserving Agent invocation, Mock mode, logs, exports, and settings.

**Tech Stack:** Python 3.11, Streamlit, FastAPI, SQLite, vanilla HTML/CSS/JS, pytest.

---

## File Map

- `src/archive_view.py`: new archive-oriented view models and query helpers for recent tasks, runs, steps, artifacts, and trace summaries.
- `tests/test_archive_view.py`: tests for archive helpers with in-memory SQLite and temporary JSONL logs.
- `frontend/tokens.css`: Archive OS color, type, spacing, motion, and surface tokens.
- `frontend/styles.css`: static frontend layouts, file cards, index rows, dossier panels, evidence panels, responsive rules, and motion CSS.
- `frontend/main.js`: scan cursor, scroll reveal, pointer tilt, active nav, and workbench link behavior.
- `frontend/index.html`: Archive Entrance homepage.
- `frontend/*-agent.html`: ten Agent File pages using a shared structure.
- `frontend/streamlit-theme.css`: Archive Desk skin for Streamlit controls and panels.
- `app.py`: Streamlit Archive Desk restructure with Task File, Agent Index, Run Dossier, Evidence Chain, Export Vault, and Settings tabs.
- `docs/superpowers/specs/2026-05-31-operai-archive-os-redesign-design.md`: source spec, already written.

## Task 1: Initialize Repository Baseline

**Files:**
- Modify: `.gitignore`
- Commit: current source baseline after ignore rules

- [ ] **Step 1: Verify ignored generated data**

Run:

```powershell
git status --short --ignored
```

Expected: `.env`, `data/`, caches, and `.superpowers/` are ignored.

- [ ] **Step 2: Commit baseline**

Run:

```powershell
git add .
git commit -m "chore: baseline operai mvp"
```

Expected: baseline commit succeeds. If git identity is missing, set local identity:

```powershell
git config user.name "Codex"
git config user.email "codex@example.local"
git commit -m "chore: baseline operai mvp"
```

## Task 2: Add Archive View Data Layer

**Files:**
- Create: `src/archive_view.py`
- Create: `tests/test_archive_view.py`

- [ ] **Step 1: Write tests for archive summaries**

Create `tests/test_archive_view.py` with tests that initialize an in-memory database, insert one task, one run, two steps, one artifact bundle, and one JSONL trace file. Assert:

```python
from src.archive_view import (
    build_archive_summary,
    build_evidence_chain,
    list_agent_files,
    load_run_dossier,
)


def test_list_agent_files_contains_ten_agents():
    agents = list_agent_files()
    assert len(agents) == 10
    assert agents["D"]["title"] == "数据运营"
    assert agents["C"]["archive_role"]


def test_load_run_dossier_returns_steps_and_artifacts(tmp_path, conn_with_archive_rows):
    dossier = load_run_dossier(conn_with_archive_rows, tmp_path, "run-1")
    assert dossier["run_id"] == "run-1"
    assert dossier["status"] == "success"
    assert [s["step"] for s in dossier["steps"]] == ["D", "C"]
    assert dossier["agent_outputs"]["D"]["insights"] == ["洞察"]


def test_build_evidence_chain_extracts_metrics_and_trace(tmp_path, conn_with_archive_rows):
    chain = build_evidence_chain(conn_with_archive_rows, tmp_path, "run-1")
    assert chain["trace_events"][0]["event"] == "run_start"
    assert chain["nodes"][0]["label"] == "Raw Input"
    assert chain["nodes"][-1]["label"] == "Export Readiness"


def test_build_archive_summary_counts_runs(tmp_path, conn_with_archive_rows):
    summary = build_archive_summary(conn_with_archive_rows, tmp_path)
    assert summary["agent_count"] == 10
    assert summary["run_count"] == 1
    assert summary["latest_run"]["id"] == "run-1"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_archive_view.py -q
```

Expected: FAIL because `src.archive_view` does not exist.

- [ ] **Step 3: Implement archive view helpers**

Create `src/archive_view.py` with:

```python
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


def _trace_path(logs_dir: Path, run_id: str) -> Path:
    return logs_dir / f"{run_id}.jsonl"


def load_trace_events(logs_dir: Path, run_id: str, limit: int = 80) -> list[dict[str, Any]]:
    path = _trace_path(logs_dir, run_id)
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({"event": "unparsed", "raw": line[:500]})
    return events[-limit:]


def load_run_dossier(conn: sqlite3.Connection, logs_dir: Path, run_id: str) -> dict[str, Any]:
    runs = query_all(conn, "SELECT * FROM runs WHERE id=?", (run_id,))
    if not runs:
        return {}
    run = runs[0]
    steps = [dict(r) for r in query_all(conn, "SELECT step, status, duration_ms, output_summary, raw_json FROM run_steps WHERE run_id=? ORDER BY id", (run_id,))]
    artifacts = query_all(conn, "SELECT drafts_final_json, drafts_json FROM artifacts WHERE run_id=?", (run_id,))
    bundle = {}
    if artifacts:
        bundle = _json_loads(artifacts[0]["drafts_final_json"] or artifacts[0]["drafts_json"], {})
    return {
        "run_id": run_id,
        "task_id": run["task_id"],
        "status": run["status"],
        "mock": bool(run["mock"]),
        "pack_id": run["pack_id"] if "pack_id" in run.keys() else "media",
        "started_at": run["started_at"],
        "finished_at": run["finished_at"],
        "error_message": run["error_message"],
        "steps": steps,
        "agent_outputs": bundle.get("agent_outputs") or {
            "D": bundle.get("d_agent", {}),
            "C": bundle.get("c_agent", {}),
            "N": bundle.get("n_agent", {}),
        },
        "trace_events": load_trace_events(logs_dir, run_id),
    }


def build_evidence_chain(conn: sqlite3.Connection, logs_dir: Path, run_id: str) -> dict[str, Any]:
    dossier = load_run_dossier(conn, logs_dir, run_id)
    outputs = dossier.get("agent_outputs") or {}
    nodes = [
        {"label": "Raw Input", "status": "captured"},
        {"label": "Metrics", "status": "ready" if outputs.get("D", {}).get("_metrics") else "implicit"},
        {"label": "D Insight", "status": "ready" if outputs.get("D") else "missing"},
        {"label": "C Draft", "status": "ready" if outputs.get("C") else "missing"},
        {"label": "N Schedule", "status": "ready" if outputs.get("N") else "missing"},
        {"label": "Export Readiness", "status": "ready" if dossier.get("status") in {"success", "need_review"} else "blocked"},
    ]
    return {"run_id": run_id, "nodes": nodes, "trace_events": dossier.get("trace_events", [])}


def build_archive_summary(conn: sqlite3.Connection, logs_dir: Path) -> dict[str, Any]:
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
```

- [ ] **Step 4: Run archive tests**

Run:

```powershell
python -m pytest tests/test_archive_view.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/archive_view.py tests/test_archive_view.py
git commit -m "feat: add archive view layer"
```

## Task 3: Rebuild Static Design System

**Files:**
- Modify: `frontend/tokens.css`
- Modify: `frontend/styles.css`
- Modify: `frontend/main.js`

- [ ] **Step 1: Replace tokens**

Define Archive OS tokens: paper, ink, archive brown, vermilion, evidence black, serif/sans/mono stacks, spacing, hard borders, motion timing.

- [ ] **Step 2: Replace CSS components**

Implement reusable classes: `.archive-shell`, `.archive-nav`, `.file-card`, `.index-row`, `.stamp`, `.dossier-panel`, `.evidence-panel`, `.trace-node`, `.ledger-table`, `.scan-layer`, `.reveal`, responsive breakpoints, and `prefers-reduced-motion`.

- [ ] **Step 3: Replace JS motion layer**

Implement vanilla JS for:

```js
initWorkbenchLinks();
initRevealObserver();
initPointerScan();
initTiltCards();
initActiveNav();
```

Each function should no-op safely when matching elements are absent.

- [ ] **Step 4: Smoke static assets**

Run:

```powershell
python -m pytest tests/test_w1_demo_smoke.py -q
```

Expected: PASS, confirming no core imports broke.

- [ ] **Step 5: Commit**

Run:

```powershell
git add frontend/tokens.css frontend/styles.css frontend/main.js
git commit -m "feat: add archive os frontend system"
```

## Task 4: Rebuild Static Pages

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/d-agent.html`
- Modify: `frontend/u-agent.html`
- Modify: `frontend/c-agent.html`
- Modify: `frontend/a-agent.html`
- Modify: `frontend/n-agent.html`
- Modify: `frontend/f-agent.html`
- Modify: `frontend/m-agent.html`
- Modify: `frontend/p-agent.html`
- Modify: `frontend/s-agent.html`
- Modify: `frontend/e-agent.html`

- [ ] **Step 1: Replace homepage**

Homepage sections:

```text
Archive Hero
Archive System Map
Agent Index
Evidence Chain
Deployment Ledger
Final Vault CTA
```

- [ ] **Step 2: Replace Agent pages**

Each page uses this structure:

```text
Agent File Header
Role In Archive
Input Ledger
Output Ledger
Validation Rules
Example Dossier
Related Chain
Workbench CTA
```

- [ ] **Step 3: Start static server**

Run:

```powershell
python serve.py
```

Expected: server prints `OperAI: http://127.0.0.1:8080/`.

- [ ] **Step 4: Browser inspect**

Open:

```text
http://127.0.0.1:8080/
http://127.0.0.1:8080/c-agent.html
```

Expected: Archive OS visual language appears, navigation works, no horizontal overflow at desktop or mobile widths.

- [ ] **Step 5: Commit**

Run:

```powershell
git add frontend/*.html
git commit -m "feat: rebuild archive os static pages"
```

## Task 5: Rebuild Streamlit Archive Desk

**Files:**
- Modify: `frontend/streamlit-theme.css`
- Modify: `app.py`

- [ ] **Step 1: Replace Streamlit theme**

Add Archive Desk styling for body, sidebar, tabs, buttons, inputs, text areas, expanders, metrics, status stamps, evidence panels, and reduced motion.

- [ ] **Step 2: Restructure `app.py`**

Preserve existing imports and execution behavior, but reorganize UI into:

```python
tabs = st.tabs([
    "Task File",
    "Agent Index",
    "Run Dossier",
    "Evidence Chain",
    "Export Vault",
    "Settings",
])
```

Task File runs selected Agent through `invoke()` as currently done. Run Dossier renders `last_result`. Evidence Chain renders metrics and trace summaries. Export Vault uses existing `build_campaign_markdown` and Docx helpers.

- [ ] **Step 3: Add archive view integration**

Use `build_archive_summary`, `list_agent_files`, `load_run_dossier`, and `build_evidence_chain` for sidebar/archive panels.

- [ ] **Step 4: Syntax/import check**

Run:

```powershell
python -m py_compile app.py src/archive_view.py
```

Expected: no output and exit code 0.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
$env:OPERAI_MOCK="1"
python -m pytest tests/test_agent_contracts.py tests/test_pipeline.py tests/test_export_md.py tests/test_export_docx.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add app.py frontend/streamlit-theme.css
git commit -m "feat: rebuild streamlit archive desk"
```

## Task 6: Full Verification And Polish

**Files:**
- Modify as needed: frontend and Streamlit files touched above

- [ ] **Step 1: Run full test suite**

Run:

```powershell
$env:OPERAI_MOCK="1"
python -m pytest -q
```

Expected: PASS.

- [ ] **Step 2: Start workbench**

Run:

```powershell
streamlit run app.py
```

Expected: Streamlit starts at `http://localhost:8501`.

- [ ] **Step 3: Visual verification**

Check:

```text
http://127.0.0.1:8080/
http://127.0.0.1:8080/c-agent.html
http://127.0.0.1:8501
```

Expected:

- No horizontal overflow.
- Motion visible on homepage.
- Mouse scan/tilt does not block clicks.
- Workbench can run one Mock Agent.
- Run Dossier and Evidence Chain show useful state.
- Export Vault still provides Markdown/Docx content.

- [ ] **Step 4: Final commit**

Run:

```powershell
git add .
git commit -m "polish: verify archive os redesign"
```

Expected: commit if polish changes exist; otherwise report clean tree.

