from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_llm_settings_for_step_split() -> None:
    from src.llm_runtime import (
        set_model_c_override,
        set_model_d_override,
        set_split_models_override,
    )
    from src.orchestrator import llm_settings_for_step, load_config

    set_split_models_override(True)
    set_model_d_override("model-small")
    set_model_c_override("model-large")
    cfg = load_config(ROOT)
    d_cfg = llm_settings_for_step(cfg, "D")
    c_cfg = llm_settings_for_step(cfg, "C")
    assert d_cfg["model"] == "model-small"
    assert c_cfg["model"] == "model-large"
    set_split_models_override(None)
    set_model_d_override(None)
    set_model_c_override(None)


def test_llm_settings_for_step_unified() -> None:
    from src.llm_runtime import set_model_override, set_split_models_override
    from src.orchestrator import llm_settings_for_step, load_config

    set_split_models_override(False)
    set_model_override("unified-x")
    cfg = load_config(ROOT)
    assert llm_settings_for_step(cfg, "D")["model"] == "unified-x"
    set_split_models_override(None)
    set_model_override(None)
