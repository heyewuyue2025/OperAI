from __future__ import annotations

from src.export_campaign import build_campaign_markdown


def _minimal_bundle() -> tuple[dict, dict, dict]:
    d_out = {
        "insights": ["洞察 A"],
        "angles": ["角度 1"],
        "risk_flags": ["风险 X"],
        "evidence_spans": [{"field": "raw_input", "snippet": "摘录"}],
    }
    c_out = {
        "drafts": {"weibo": "微博正文", "wechat": "公众号"},
        "title_variants": ["标题一"],
    }
    n_out = {
        "schedule_suggestions": [{"platform": "weibo", "window": "18:00", "reason": "晚高峰"}],
        "hashtags": ["#tag"],
        "platform_notes": {"weibo": "注意长度"},
    }
    return d_out, c_out, n_out


def test_build_markdown_basic() -> None:
    d, c, n = _minimal_bundle()
    md = build_campaign_markdown(
        title="T",
        task_id="tid",
        run_id="rid",
        pack_id="archive",
        dag=["D", "C", "N"],
        agent_outputs={"D": d, "C": c, "N": n},
    )
    # Campaign Package 格式：章节标题用 AGENT_LABELS 渲染
    assert "数据洞察与证据（D-Agent）" in md
    assert "微博正文" in md
    assert "渠道与排期（N-Agent）" in md


def test_build_markdown_overrides() -> None:
    d, c, n = _minimal_bundle()
    md = build_campaign_markdown(
        title="T",
        task_id="tid",
        run_id="rid",
        pack_id="archive",
        dag=["D", "C", "N"],
        agent_outputs={"D": d, "C": c, "N": n},
        draft_overrides={"weibo": "已人工改写"},
    )
    assert "已人工改写" in md
    assert "微博正文" not in md
