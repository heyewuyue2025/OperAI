"""SQLite minimal schema for tasks / runs / steps."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  brand_voice TEXT,
  platforms_json TEXT,
  raw_input TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  status TEXT NOT NULL,
  demo_mode INTEGER NOT NULL DEFAULT 0,
  mock INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS run_steps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  step TEXT NOT NULL,
  status TEXT NOT NULL,
  input_summary TEXT,
  output_summary TEXT,
  duration_ms INTEGER,
  raw_json TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS artifacts (
  run_id TEXT PRIMARY KEY,
  drafts_json TEXT,
  drafts_final_json TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(id)
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def _migrate_v2(conn: sqlite3.Connection) -> None:
    """W1：tasks/runs 增加流程 ID、tasks 增加 dag_json（幂等）。"""
    additions = [
        ("tasks", "pack_id", "TEXT DEFAULT 'archive'"),
        ("tasks", "dag_json", "TEXT"),
        ("runs", "pack_id", "TEXT DEFAULT 'archive'"),
    ]
    for table, column, typedef in additions:
        if not _column_exists(conn, table, column):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {typedef}")
    conn.commit()


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate_v2(conn)


def execute(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> None:
    conn.execute(sql, params)
    conn.commit()


def query_all(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    cur = conn.execute(sql, params)
    return list(cur.fetchall())
