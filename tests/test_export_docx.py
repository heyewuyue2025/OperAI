from __future__ import annotations

import pytest

pytest.importorskip("docx")

from src.export_campaign import build_campaign_docx_bytes


def test_build_docx_bytes() -> None:
    data = build_campaign_docx_bytes(
        title="t",
        task_id="tid",
        run_id="rid",
        pack_id="archive",
        dag=["D", "C", "N"],
        agent_outputs={
            "D": {"insights": ["a"], "angles": [], "risk_flags": [], "evidence_spans": []},
            "C": {"drafts": {"weibo": "文案"}, "title_variants": []},
            "N": {"schedule_suggestions": [], "hashtags": [], "platform_notes": {}},
        },
    )
    assert data[:2] == b"PK"
