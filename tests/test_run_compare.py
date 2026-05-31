from __future__ import annotations

from src.run_compare import compare_run_drafts, unified_diff_text


def test_unified_diff_same() -> None:
    assert "相同" in unified_diff_text("hello", "hello")


def test_compare_run_drafts_per_platform() -> None:
    a = {"c_out": {"drafts": {"weibo": "版本A"}}}
    b = {"c_out": {"drafts": {"weibo": "版本B"}}}
    diffs = compare_run_drafts(a, b, label_a="A", label_b="B")
    assert "weibo" in diffs
    assert "版本A" in diffs["weibo"] or "版本B" in diffs["weibo"]
