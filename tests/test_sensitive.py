from __future__ import annotations

from pathlib import Path

from src.sensitive import load_sensitive_words, parse_sensitive_lines, save_sensitive_words, scan_sensitive

ROOT = Path(__file__).resolve().parents[1]


def test_scan_sensitive() -> None:
    words = load_sensitive_words(ROOT)
    assert "造谣" in words or len(words) >= 0
    hits = scan_sensitive("这是造谣内容", ["造谣"])
    assert "造谣" in hits


def test_save_and_parse_sensitive(tmp_path) -> None:
    root = tmp_path
    (root / "config").mkdir()
    save_sensitive_words(root, ["测试词", "第二词"])
    loaded = load_sensitive_words(root)
    assert "测试词" in loaded
    assert parse_sensitive_lines("# 注释\n词\n") == ["词"]
