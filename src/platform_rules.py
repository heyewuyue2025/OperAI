"""分平台规则配置（N-Agent / C-Agent 引用）。"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def load_platform_rules(root: Path) -> dict[str, Any]:
    path = root / "config" / "platform_rules.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def rules_for_platforms(root: Path, platforms: list[str]) -> dict[str, Any]:
    all_rules = load_platform_rules(root)
    return {p: all_rules[p] for p in platforms if p in all_rules}
