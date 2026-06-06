"""Verify Gate：archive 成功 run 不 block；敏感词可 block。"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPERAI_MOCK", "1")


def _archive_pack():
    from src.harness.pack_loader import load_pack

    return load_pack(ROOT, "archive")


def test_archive_success_run_not_blocked() -> None:
    from src.harness.verify_gate import evaluate
    from src.orchestrator import execute_pipeline, load_config, open_connection

    cfg = load_config(ROOT)
    conn = open_connection(ROOT, cfg)
    res = execute_pipeline(
        ROOT, conn, cfg,
        task_id=str(uuid.uuid4()),
        title="测试",
        brand_voice="克制",
        platforms=["weibo", "xhs"],
        raw_input="新品冷萃杯上市，强调便携、防漏和日常办公场景。",
    )
    assert res["ok"]
    pack = _archive_pack()
    vr = evaluate(
        {
            "d_out": res["d_out"],
            "c_out": res["c_out"],
            "raw_input": "新品冷萃杯上市，强调便携、防漏和日常办公场景。",
            "run_status": res["status"],
        },
        pack=pack,
        root=ROOT,
    )
    assert vr.block_export is False


def test_empty_drafts_warns_not_block() -> None:
    from src.harness.verify_gate import evaluate

    pack = _archive_pack()
    vr = evaluate({"d_out": {}, "c_out": {}, "raw_input": ""}, pack=pack, root=ROOT)
    assert vr.block_export is False
    assert any("缺少" in w or "跳过" in w for w in vr.warnings)


def test_sensitive_hit_blocks_export() -> None:
    from src.harness.verify_gate import evaluate

    pack = _archive_pack()
    vr = evaluate(
        {
            "d_out": {"risk_flags": []},
            "c_out": {
                "drafts": {
                    "weibo": "这是造谣内容需要处理",
                    "wechat": "正常新品上市说明文案",
                }
            },
            "raw_input": "测试",
        },
        pack=pack,
        root=ROOT,
    )
    assert vr.block_export is True
    assert vr.warnings
