from __future__ import annotations


def test_voice_style_presets_provide_50_choices() -> None:
    from src.voice_styles import VOICE_STYLE_PRESETS

    assert len(VOICE_STYLE_PRESETS) == 50
    assert len(set(VOICE_STYLE_PRESETS)) == 50
    assert "克制可信" in VOICE_STYLE_PRESETS
    assert "用户同理心" in VOICE_STYLE_PRESETS
    assert "避免过度承诺" in VOICE_STYLE_PRESETS


def test_merge_voice_styles_replaces_existing_style_line() -> None:
    from src.voice_styles import merge_voice_styles

    merged = merge_voice_styles(
        "表达风格：年轻活泼\n禁用词：稳赚、必火",
        ["克制可信", "清晰直接", "not-a-preset"],
    )

    assert merged.splitlines()[0] == "表达风格：克制可信、清晰直接"
    assert "年轻活泼" not in merged
    assert "禁用词：稳赚、必火" in merged
    assert "not-a-preset" not in merged
