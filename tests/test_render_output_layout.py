from __future__ import annotations


def test_generic_text_output_keeps_card_body_in_content_column(monkeypatch) -> None:
    from src import render_output

    html_fragments: list[str] = []

    def fake_markdown(body: str, *, unsafe_allow_html: bool = False) -> None:
        if "oa-output-card" in body:
            html_fragments.append(body)

    monkeypatch.setattr(render_output.st, "markdown", fake_markdown)

    render_output._render_generic_cards({"positioning": "基于当前素材的定位草稿"})

    assert html_fragments
    assert "<i>--</i><span>" in html_fragments[0]


def test_generic_dict_output_has_index_column(monkeypatch) -> None:
    from src import render_output

    html_fragments: list[str] = []

    def fake_markdown(body: str, *, unsafe_allow_html: bool = False) -> None:
        if "oa-output-card" in body:
            html_fragments.append(body)

    monkeypatch.setattr(render_output.st, "markdown", fake_markdown)

    render_output._render_generic_cards({"roi_estimate": {"summary": "可执行", "confidence": "low"}})

    assert html_fragments
    assert all("<i>" in item and "<span>" in item for item in html_fragments)
