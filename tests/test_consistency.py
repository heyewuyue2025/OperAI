from __future__ import annotations

from src.consistency import check_draft_consistency


def test_consistency_number_mismatch() -> None:
    d_out = {"risk_flags": [], "evidence_spans": [{"field": "raw_input", "snippet": "音乐节"}]}
    drafts = {
        "weibo": "下月12日活动",
        "wechat": "欢迎参加",
    }
    report = check_draft_consistency(d_out=d_out, drafts=drafts, use_llm=False)
    assert any(i.get("kind") == "number_mismatch" for i in report["issues"])


def test_consistency_ok_minimal() -> None:
    d_out = {"risk_flags": [], "evidence_spans": []}
    drafts = {"weibo": "你好", "wechat": "你好"}
    report = check_draft_consistency(d_out=d_out, drafts=drafts, use_llm=False)
    assert report["ok"] is True
