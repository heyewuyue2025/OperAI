"""多平台文案一致性检查（规则 + 可选 LLM）。"""
from __future__ import annotations

import json
import re
from typing import Any

_ISSUE = dict[str, Any]

# 夸大/绝对化表述（与 D-Agent risk 呼应）
_HYPE_PATTERNS = [
    r"全网第一",
    r"guaranteed|100%|绝对保证|史上最强|必火|躺赚",
    r"官方承诺",
]


def _extract_numbers(text: str) -> set[str]:
    found: set[str] = set()
    for m in re.finditer(r"\d{1,4}(?:\.\d+)?%?", text):
        found.add(m.group(0))
    for m in re.finditer(r"[一二三四五六七八九十百千万]+[个次场天日月年]", text):
        found.add(m.group(0))
    return found


def _check_heuristic(
    *,
    d_out: dict[str, Any],
    drafts: dict[str, str],
    raw_input: str,
) -> list[_ISSUE]:
    issues: list[_ISSUE] = []
    platforms = list(drafts.keys())
    nums_by_plat = {p: _extract_numbers(drafts[p]) for p in platforms}

    all_nums: set[str] = set()
    for ns in nums_by_plat.values():
        all_nums |= ns

    for num in all_nums:
        holders = [p for p, ns in nums_by_plat.items() if num in ns]
        if 0 < len(holders) < len(platforms):
            missing = [p for p in platforms if p not in holders]
            issues.append(
                {
                    "severity": "warn",
                    "kind": "number_mismatch",
                    "message": f"数字「{num}」出现在 {', '.join(holders)}，但未在 {', '.join(missing)} 中出现，请核对是否同一事实。",
                    "platforms": holders + missing,
                }
            )

    risks = [str(x) for x in (d_out.get("risk_flags") or [])]
    risk_text = " ".join(risks)
    banned_hints: list[str] = []
    if "饮酒" in risk_text or "酒精" in risk_text:
        banned_hints.extend(["酒", "白酒", "啤酒", "干杯", "畅饮"])
    for plat, text in drafts.items():
        for hint in banned_hints:
            if hint in text:
                issues.append(
                    {
                        "severity": "error",
                        "kind": "risk_violation",
                        "message": f"「{plat}」文案含「{hint}」，与洞察风险「{risk_text[:40]}…」可能冲突。",
                        "platforms": [plat],
                    }
                )

    for plat, text in drafts.items():
        for pat in _HYPE_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                issues.append(
                    {
                        "severity": "warn",
                        "kind": "hype_language",
                        "message": f"「{plat}」含夸大或绝对化表述，建议改为可验证描述。",
                        "platforms": [plat],
                    }
                )

    evidence = d_out.get("evidence_spans") or []
    snippets = [str(e.get("snippet", "")) for e in evidence if isinstance(e, dict)]
    if snippets and raw_input:
        for plat, text in drafts.items():
            if not any(s and s in text for s in snippets if len(s) >= 4):
                issues.append(
                    {
                        "severity": "info",
                        "kind": "evidence_weak",
                        "message": f"「{plat}」未明显引用洞察证据摘录，建议对齐可溯源表述。",
                        "platforms": [plat],
                    }
                )

    return issues


def _check_llm(
    *,
    d_out: dict[str, Any],
    drafts: dict[str, str],
    llm_cfg: dict[str, Any],
) -> list[_ISSUE]:
    from src.llm_json import chat_json_parse

    system = (
        "你是内容质检编辑。比较多平台文案与洞察，找出事实矛盾、口径冲突、违反 risk_flags 的表述。"
        "只输出 JSON：issues 为数组，每项含 severity（error|warn|info）、message（中文）、platforms（平台 id 数组）。"
        "无问题则 issues 为空数组。"
    )
    user = json.dumps(
        {"insights": d_out, "drafts": drafts},
        ensure_ascii=False,
    )
    try:
        out = chat_json_parse(system=system, user=user, llm_cfg=llm_cfg, max_tokens=800)
        raw = out.get("issues") or []
        issues: list[_ISSUE] = []
        for item in raw:
            if isinstance(item, dict) and item.get("message"):
                issues.append(
                    {
                        "severity": str(item.get("severity", "warn")),
                        "kind": "llm",
                        "message": str(item["message"]),
                        "platforms": list(item.get("platforms") or []),
                    }
                )
        return issues
    except Exception:  # noqa: BLE001
        return []


def check_draft_consistency(
    *,
    d_out: dict[str, Any],
    drafts: dict[str, str],
    raw_input: str = "",
    use_llm: bool = False,
    llm_cfg: dict[str, Any] | None = None,
    sensitive_words: list[str] | None = None,
) -> dict[str, Any]:
    """返回 { ok, issues, summary }；ok 表示无 error 级问题。"""
    cleaned = {k: (v or "").strip() for k, v in drafts.items() if (v or "").strip()}
    if len(cleaned) < 2:
        return {"ok": True, "issues": [], "summary": "至少需要两个平台文案才能做交叉比对。"}

    issues = _check_heuristic(d_out=d_out, drafts=cleaned, raw_input=raw_input)
    if sensitive_words:
        from src.sensitive import scan_sensitive

        for plat, text in cleaned.items():
            hits = scan_sensitive(text, sensitive_words)
            for w in hits:
                issues.append(
                    {
                        "severity": "error",
                        "kind": "sensitive_word",
                        "message": f"「{plat}」命中敏感词「{w}」，请修改或删除。",
                        "platforms": [plat],
                    }
                )
    if use_llm and llm_cfg:
        issues.extend(_check_llm(d_out=d_out, drafts=cleaned, llm_cfg=llm_cfg))

    # 去重 message
    seen: set[str] = set()
    unique: list[_ISSUE] = []
    for it in issues:
        key = it.get("message", "")
        if key in seen:
            continue
        seen.add(key)
        unique.append(it)

    errors = [i for i in unique if i.get("severity") == "error"]
    warns = [i for i in unique if i.get("severity") == "warn"]
    ok = len(errors) == 0
    if not unique:
        summary = "未发现明显跨平台冲突，仍建议人工终审。"
    elif ok:
        summary = f"发现 {len(warns)} 条提示、0 条阻断项，请酌情修改。"
    else:
        summary = f"发现 {len(errors)} 条阻断项、{len(warns)} 条提示，建议修改后再导出。"

    return {"ok": ok, "issues": unique, "summary": summary}
