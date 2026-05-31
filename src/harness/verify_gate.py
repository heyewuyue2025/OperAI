"""Verify Gate：聚合一致性检查与敏感词扫描。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.consistency import check_draft_consistency
from src.harness.pack_loader import PackConfig
from src.sensitive import load_sensitive_words


@dataclass(frozen=True)
class VerifyResult:
    warnings: list[str]
    block_export: bool
    checks: list[dict[str, Any]] = field(default_factory=list)


def _bundle_parts(run_bundle: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str, str | None]:
    d_out = run_bundle.get("d_out") or run_bundle.get("D") or {}
    c_out = run_bundle.get("c_out") or run_bundle.get("C") or {}
    raw_input = str(run_bundle.get("raw_input") or "")
    run_status = run_bundle.get("run_status")
    return d_out, c_out, raw_input, run_status


def evaluate(
    run_bundle: dict[str, Any],
    *,
    pack: PackConfig,
    root: Path | None = None,
) -> VerifyResult:
    """聚合验证：一致性 + 敏感词 + 流程审核策略。"""
    d_out, c_out, raw_input, run_status = _bundle_parts(run_bundle)
    drafts = dict(c_out.get("drafts") or {})
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []
    block_export = False

    sensitive_words: list[str] | None = None
    if root is not None:
        sensitive_words = load_sensitive_words(root)

    # 文案一致性检查
    if len(drafts) >= 2:
        consistency = check_draft_consistency(
            d_out=d_out,
            drafts=drafts,
            raw_input=raw_input,
            sensitive_words=sensitive_words,
        )
        checks.append({
            "id": "draft_consistency",
            "passed": consistency.get("ok", True),
            "detail": consistency.get("summary", ""),
        })
        for issue in consistency.get("issues") or []:
            msg = str(issue.get("message") or "")
            if msg:
                warnings.append(msg)
            if issue.get("severity") == "error" and issue.get("kind") == "sensitive_word":
                block_export = True
    elif not drafts:
        warnings.append("缺少多平台文案，跳过跨平台一致性检查。")
        checks.append({"id": "draft_consistency", "passed": True, "detail": "无 drafts"})

    # 流程审核策略
    verify_cfg = pack.verify or {}
    if verify_cfg.get("block_export_until_review") and run_status == "need_review":
        block_export = True
        warnings.append("流程策略：审核完成前禁止导出。")
        checks.append({
            "id": "pack_review_gate",
            "passed": False,
            "detail": "需人工标记「已核对」后才可导出",
        })

    if verify_cfg.get("require_risk_flags_ack"):
        risks = d_out.get("risk_flags") or []
        if risks:
            warnings.append(f"请确认已阅读 {len(risks)} 条风险标记后再导出：{'、'.join(str(r)[:60] for r in risks[:5])}")
            checks.append({
                "id": "risk_flags_ack",
                "passed": False,
                "detail": f"共 {len(risks)} 条风险标记待确认",
            })

    return VerifyResult(warnings=warnings, block_export=block_export, checks=checks)
