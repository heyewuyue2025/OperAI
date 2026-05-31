"""运行时 LLM 配置覆盖（由设置页写入，编排器读取）。"""
from __future__ import annotations

import os
from typing import Any

_mock_override: bool | None = None
_model_override: str | None = None
_temperature_override: float | None = None
_skip_review_override: bool | None = None
_short_output_override: bool | None = None
_split_models_override: bool | None = None
_model_d_override: str | None = None
_model_c_override: str | None = None


def set_mock_override(value: bool | None) -> None:
    global _mock_override
    _mock_override = value


def set_model_override(value: str | None) -> None:
    global _model_override
    _model_override = (value or "").strip() or None


def set_temperature_override(value: float | None) -> None:
    global _temperature_override
    _temperature_override = value


def set_skip_review_override(value: bool | None) -> None:
    global _skip_review_override
    _skip_review_override = value


def effective_use_llm() -> bool:
    if _mock_override is True:
        return False
    if os.getenv("OPERAI_MOCK", "").strip() == "1":
        return False
    if _mock_override is False:
        return bool(os.getenv("OPENAI_API_KEY", "").strip())
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def effective_skip_review(cfg: dict[str, Any]) -> bool:
    if _skip_review_override is not None:
        return _skip_review_override
    return bool(cfg.get("demo_mode", {}).get("skip_review"))


def set_short_output_override(value: bool | None) -> None:
    global _short_output_override
    _short_output_override = value


def effective_short_output(cfg: dict[str, Any]) -> bool:
    if _short_output_override is not None:
        return _short_output_override
    return bool(cfg.get("demo_mode", {}).get("short_output"))


def set_split_models_override(value: bool | None) -> None:
    global _split_models_override
    _split_models_override = value


def set_model_d_override(value: str | None) -> None:
    global _model_d_override
    _model_d_override = (value or "").strip() or None


def set_model_c_override(value: str | None) -> None:
    global _model_c_override
    _model_c_override = (value or "").strip() or None


def effective_split_models() -> bool:
    return bool(_split_models_override)


def model_for_step(cfg: dict[str, Any], step: str) -> str:
    """D 用小模型、C 用大模型；N 沿用统一模型。"""
    import os

    lc = cfg.get("llm", {})
    step = step.upper()
    default = _model_override or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if step == "D":
        return _model_d_override or lc.get("model_d") or os.getenv("OPENAI_MODEL_D", "gpt-4o-mini")
    if step == "C":
        return _model_c_override or lc.get("model_c") or os.getenv("OPENAI_MODEL_C", "gpt-4o")
    return default


def sync_from_session(session: Any) -> None:
    """将 Streamlit session_state 同步到运行时覆盖。"""
    if "operai_force_mock" in session:
        set_mock_override(bool(session["operai_force_mock"]))
    if session.get("operai_model"):
        set_model_override(str(session["operai_model"]))
    if "operai_temperature" in session:
        set_temperature_override(float(session["operai_temperature"]))
    if "operai_skip_review" in session:
        set_skip_review_override(bool(session["operai_skip_review"]))
    if "operai_short_output" in session:
        set_short_output_override(bool(session["operai_short_output"]))
    if "operai_split_models" in session:
        set_split_models_override(bool(session["operai_split_models"]))
    if session.get("operai_model_d"):
        set_model_d_override(str(session["operai_model_d"]))
    if session.get("operai_model_c"):
        set_model_c_override(str(session["operai_model_c"]))


def apply_llm_cfg(base: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    if _model_override:
        out["model"] = _model_override
    if _temperature_override is not None:
        out["temperature"] = float(_temperature_override)
    return out
