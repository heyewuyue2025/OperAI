from __future__ import annotations

import pytest

from src.llm_json import parse_json_object, strip_markdown_fence


def test_strip_markdown_fence() -> None:
    raw = "```json\n{\"a\": 1}\n```"
    assert strip_markdown_fence(raw) == '{"a": 1}'


def test_parse_with_preamble() -> None:
    text = "下面是结果：\n\n```json\n{\"x\": \"y\"}\n```\n谢谢"
    assert parse_json_object(text)["x"] == "y"


def test_slice_outer_object() -> None:
    s = 'noise {"k": [1,2]} tail'
    assert parse_json_object(s)["k"] == [1, 2]


def test_parse_rejects_non_object_root() -> None:
    with pytest.raises(ValueError):
        parse_json_object("[1,2,3]")
