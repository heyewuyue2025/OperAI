"""Verify Gate：聚合一致性检查与敏感词扫描，支持行业 Pack 差异化策略。"""
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


_FINANCE_MUST_PATTERNS: list[tuple[str, str, str]] = [
    # (检查项, 正则/关键词, 错误信息)
    ("risk_disclaimer", r"风险|不保本|不保证", "金融内容须包含风险提示语句（如「投资需谨慎」「不保证收益」）"),
    ("no_return_promise", r"承诺收益|保证本金|稳赚|必赚|只赚|躺赚|暴富|刚性兑付|包赚", "禁止承诺收益或暗示保本"),
]

_FINANCE_POSITIVE_PATTERNS = [
    # 这些表述只有在肯定语境下才违规；前面有「不/非/无」时跳过
    (r"(?<!不)(?<!非)(?<!无)保本(?!型|类|基金|理财)", "禁止暗示保本（发现「保本」表述）"),
    (r"(?<!不)(?<!非)(?<!无)保证收益", "禁止保证收益（发现「保证收益」表述）"),
]


def _check_finance_compliance(text: str) -> list[dict[str, Any]]:
    """金融场景专项合规扫描。"""
    import re
    issues: list[dict[str, Any]] = []

    # 检查是否缺少风险提示
    has_risk = bool(re.search(r"风险|投资需谨慎|不保本|不保证|本产品", text))
    if not has_risk:
        issues.append({
            "severity": "error",
            "kind": "finance_missing_risk",
            "message": "金融内容缺少风险提示，请在文案中显式加入风险披露语句。",
            "platforms": [],
        })

    # 检查承诺收益/保本表述（仅肯定语境）
    for check_id, pattern, msg in _FINANCE_MUST_PATTERNS:
        if check_id == "risk_disclaimer":
            continue
        if re.search(pattern, text):
            issues.append({
                "severity": "error",
                "kind": f"finance_{check_id}",
                "message": msg,
                "platforms": [],
            })

    # 检查保本（排除「不保本」等否定语境）
    for pattern, msg in _FINANCE_POSITIVE_PATTERNS:
        if re.search(pattern, text):
            issues.append({
                "severity": "error",
                "kind": "finance_positive_baoben",
                "message": msg,
                "platforms": [],
            })

    return issues


def evaluate(
    run_bundle: dict[str, Any],
    *,
    pack: PackConfig,
    root: Path | None = None,
) -> VerifyResult:
    """聚合验证：一致性 + 敏感词 + Pack 特定策略。"""
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
            if issue.get("severity") == "error":
                # 金融 Pack：所有 error 级问题均阻断导出
                if pack.id == "finance":
                    block_export = True
                elif issue.get("kind") == "sensitive_word":
                    # 非金融 Pack：仅敏感词 error 阻断
                    block_export = True
    elif not drafts:
        warnings.append("缺少多平台文案，跳过跨平台一致性检查。")
        checks.append({"id": "draft_consistency", "passed": True, "detail": "无 drafts"})

    # 金融 Pack 专项合规
    if pack.id == "finance":
        all_text = " ".join(drafts.values()) + " " + raw_input
        finance_issues = _check_finance_compliance(all_text)
        if finance_issues:
            checks.append({
                "id": "finance_compliance",
                "passed": False,
                "detail": f"发现 {len(finance_issues)} 项金融合规问题",
            })
            for fi in finance_issues:
                warnings.append(fi["message"])
                if fi.get("severity") == "error":
                    block_export = True
        else:
            checks.append({"id": "finance_compliance", "passed": True, "detail": "金融合规扫描通过"})

    # Pack 审核策略
    verify_cfg = pack.verify or {}
    if verify_cfg.get("block_export_until_review") and run_status == "need_review":
        block_export = True
        warnings.append("Pack 策略：审核完成前禁止导出。")
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
