from __future__ import annotations


def test_display_labels_translate_internal_json_keys() -> None:
    from src.display_labels import label_value

    text = label_value(
        {
            "phase": "准备",
            "objective": "澄清目标",
            "tasks": ["整理材料", "确认平台"],
            "owner_agent": "D",
            "channel": "weibo",
            "percent_range": "20%-30%",
        }
    )

    assert "phase" not in text
    assert "objective" not in text
    assert "owner_agent" not in text
    assert "weibo" not in text
    assert "阶段：准备" in text
    assert "目标：澄清目标" in text
    assert "协作智能体：材料洞察（D）" in text
    assert "渠道：微博" in text
    assert "预算区间：20%-30%" in text


def test_display_labels_translate_output_section_keys_and_status() -> None:
    from src.display_labels import label_key, label_value

    assert label_key("community_actions") == "社群动作"
    assert label_key("kol_hints") == "KOL 与共创"
    assert label_key("engagement_scripts") == "互动话术"
    assert label_value("wechat") == "微信公众号"
    assert label_value("success") == "成功"
    assert label_value("plan") == "方案交付"
