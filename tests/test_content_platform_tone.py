from __future__ import annotations


def test_content_fallback_generates_platform_native_drafts() -> None:
    from src.agents.c_agent import run_c

    raw_input = (
        "我们是一家面向年轻白领的即饮燕麦拿铁品牌，主打低糖、高纤维、轻负担，"
        "准备上线新品「黑芝麻燕麦拿铁」。目标用户是 22-35 岁一二线城市女性，"
        "常见场景是早餐代餐、下午犯困、健身后补充能量。不能夸大减肥、治疗、养生功效。"
    )

    out = run_c(
        use_llm=False,
        d_out={},
        platforms=["weibo", "wechat", "xhs", "bilibili", "douyin", "kuaishou"],
        raw_input=raw_input,
        brand_voice="轻松但不油腻，有生活感，不要太保健品",
        llm_cfg={},
    )

    drafts = out["drafts"]
    assert set(drafts) == {"weibo", "wechat", "xhs", "bilibili", "douyin", "kuaishou"}
    assert "#黑芝麻燕麦拿铁#" in drafts["weibo"]
    assert "标题" in drafts["wechat"] and "正文" in drafts["wechat"]
    assert "适合" in drafts["xhs"] and "｜" in drafts["xhs"]
    assert "本期看点" in drafts["bilibili"]
    assert "开头" in drafts["douyin"] and "镜头" in drafts["douyin"]
    assert "说人话" in drafts["kuaishou"] or "真实" in drafts["kuaishou"]
    assert all("我们是一家面向年轻白领" not in text for text in drafts.values())


def test_content_fallback_keeps_compliance_boundary() -> None:
    from src.agents.c_agent import run_c

    out = run_c(
        use_llm=False,
        d_out={},
        platforms=["xhs", "douyin"],
        raw_input="新品是低糖高纤维黑芝麻燕麦拿铁，不能夸大减肥、治疗、养生功效。",
        brand_voice="克制可信",
        llm_cfg={},
    )

    joined = "\n".join(out["drafts"].values())
    assert "减肥" not in joined
    assert "治疗" not in joined
    assert any("功效" in note or "合规" in note for note in out["compliance_notes"])
