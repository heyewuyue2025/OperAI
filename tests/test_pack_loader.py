"""流程加载：archive 默认 DAG D→C→N。"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_load_archive_pack() -> None:
    from src.harness.pack_loader import load_pack

    pack = load_pack(ROOT, "archive")
    assert pack.id == "archive"
    assert pack.name
    assert "weibo" in pack.default_platforms


def test_archive_default_dag_is_dcn() -> None:
    from src.harness.pack_loader import load_pack

    pack = load_pack(ROOT, "archive")
    assert pack.default_dag == ["D", "C", "N"]


def test_list_packs_includes_archive() -> None:
    from src.harness.pack_loader import list_packs

    ids = [p.id for p in list_packs(ROOT)]
    assert "archive" in ids


def test_load_unknown_pack_raises() -> None:
    from src.harness.pack_loader import load_pack

    with pytest.raises(FileNotFoundError):
        load_pack(ROOT, "nonexistent_pack_xyz")


def test_db_migration_idempotent(tmp_path: Path) -> None:
    from src.storage.db import connect, init_db

    db_path = tmp_path / "test.sqlite3"
    conn = connect(db_path)
    init_db(conn)
    init_db(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    assert "pack_id" in cols
    assert "dag_json" in cols
    run_cols = {r[1] for r in conn.execute("PRAGMA table_info(runs)").fetchall()}
    assert "pack_id" in run_cols
    conn.close()
