"""敏感词表加载、会话覆盖与写回。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

SESSION_KEY = "operai_sensitive_words"


def sensitive_words_path(root: Path) -> Path:
    return root / "config" / "sensitive_words.txt"


def parse_sensitive_lines(text: str) -> list[str]:
    words: list[str] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        words.append(line)
    return words


def load_sensitive_words(root: Path) -> list[str]:
    path = sensitive_words_path(root)
    if not path.is_file():
        return []
    return parse_sensitive_lines(path.read_text(encoding="utf-8"))


def save_sensitive_words(root: Path, words: list[str]) -> None:
    path = sensitive_words_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    cleaned = [w.strip() for w in words if w and w.strip() and not w.strip().startswith("#")]
    header = "# 每行一个词或短语；# 开头为注释\n"
    body = "\n".join(cleaned)
    path.write_text(f"{header}{body}\n" if body else header, encoding="utf-8")


def effective_sensitive_words(root: Path, session: Any | None = None) -> list[str]:
    """优先使用设置页写入的会话覆盖，否则读文件。"""
    if session is not None:
        override = session.get(SESSION_KEY)
        if override is not None:
            return list(override)
    return load_sensitive_words(root)


def scan_sensitive(text: str, words: list[str]) -> list[str]:
    if not text or not words:
        return []
    hits: list[str] = []
    for w in words:
        if w and w in text:
            hits.append(w)
    return hits
