"""两次 run 的 C 文案简易对比。"""
from __future__ import annotations

import difflib
from typing import Any

PLATFORM_LABELS = {"weibo": "微博", "wechat": "微信公众号", "xhs": "小红书", "bilibili": "哔哩哔哩", "douyin": "抖音", "kuaishou": "快手"}


def extract_drafts(bundle: dict[str, Any] | None) -> dict[str, str]:
    if not bundle:
        return {}
    c_out = bundle.get("c_out") or {}
    return {k: str(v) for k, v in (c_out.get("drafts") or {}).items()}


def unified_diff_text(a: str, b: str, *, label_a: str = "A", label_b: str = "B") -> str:
    lines = list(
        difflib.unified_diff(
            a.splitlines(),
            b.splitlines(),
            fromfile=label_a,
            tofile=label_b,
            lineterm="",
        )
    )
    if not lines:
        return "（两版文案相同）"
    return "\n".join(lines)


def compare_run_drafts(
    bundle_a: dict[str, Any] | None,
    bundle_b: dict[str, Any] | None,
    *,
    label_a: str = "Run A",
    label_b: str = "Run B",
) -> dict[str, str]:
    """按平台返回 unified diff 文本。"""
    da = extract_drafts(bundle_a)
    db = extract_drafts(bundle_b)
    plats = sorted(set(da.keys()) | set(db.keys()))
    out: dict[str, str] = {}
    for plat in plats:
        text_a = da.get(plat, "")
        text_b = db.get(plat, "")
        plat_label = PLATFORM_LABELS.get(plat, plat)
        out[plat] = unified_diff_text(
            text_a,
            text_b,
            label_a=f"{label_a}/{plat_label}",
            label_b=f"{label_b}/{plat_label}",
        )
    return out
