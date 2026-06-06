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
    assert "冰箱" in drafts["xhs"] and "｜" in drafts["xhs"]
    assert "本期看点" in drafts["bilibili"]
    assert "开头" in drafts["douyin"] and "镜头" in drafts["douyin"]
    assert "说人话" in drafts["kuaishou"] or "真实" in drafts["kuaishou"]
    assert all("我们是一家面向年轻白领" not in text for text in drafts.values())
    assert all("适合：" not in text and "场景：" not in text for text in drafts.values())


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


def test_content_normalizer_replaces_surface_level_platform_copy() -> None:
    from src.agents.c_agent import _normalize_platform_output

    raw_input = (
        "我们是一家面向年轻白领的即饮燕麦拿铁品牌，主打低糖、高纤维、轻负担，"
        "准备上线新品「黑芝麻燕麦拿铁」。目标用户是 22-35 岁一二线城市女性，"
        "常见场景是早餐代餐、下午犯困、健身后补充能量。"
    )
    weak = {
        "drafts": {
            "xhs": "黑芝麻燕麦拿铁｜给忙碌日常的一杯轻负担\n\n适合：22-35 岁女性\n场景：早餐代餐 / 下午犯困 / 健身后补充能量\n我会关注的 3 个点：\n- 低糖\n- 0 蔗糖添加\n- 高纤维",
            "bilibili": "标题：我们为什么做「黑芝麻燕麦拿铁」？一次新品背后的真实拆解\n\n本期看点：\n这瓶饮品对应哪些真实场景：早餐代餐 / 下午犯困 / 健身后补充能量",
        },
        "title_variants": [],
    }

    out = _normalize_platform_output(weak, raw_input, ["xhs", "bilibili"], "年轻活泼")

    assert "适合：" not in out["drafts"]["xhs"]
    assert "场景：" not in out["drafts"]["xhs"]
    assert "冰箱" in out["drafts"]["xhs"]
    assert "对应哪些真实场景" not in out["drafts"]["bilibili"]
    assert "本期看点" in out["drafts"]["bilibili"]
