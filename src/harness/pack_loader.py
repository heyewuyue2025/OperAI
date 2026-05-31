"""Pack 配置加载：YAML → PackConfig。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.agents.base import AGENT_IDS
from src.harness import plugin_registry


@dataclass(frozen=True)
class PackConfig:
    id: str
    name: str
    description: str
    default_dag: list[str]
    default_platforms: list[str]
    samples_dir: str
    verify: dict[str, Any] = field(default_factory=dict)


def _packs_root(root: Path) -> Path:
    return root / "packs"


def _validate_dag(dag: list[str], *, pack_id: str) -> list[str]:
    if not dag:
        raise ValueError(f"Pack {pack_id!r}: default_dag 不能为空")
    normalized: list[str] = []
    for step in dag:
        aid = str(step).strip().upper()
        if aid not in AGENT_IDS:
            raise ValueError(f"Pack {pack_id!r}: 非法 agent_id {step!r}")
        try:
            plugin_registry.get(aid)
        except KeyError as e:
            raise ValueError(f"Pack {pack_id!r}: agent {aid} 未在 plugin_registry 注册") from e
        normalized.append(aid)
    return normalized


def load_pack(root: Path, pack_id: str) -> PackConfig:
    path = _packs_root(root) / pack_id / "pack.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Pack 不存在: {pack_id} ({path})")
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    pid = str(raw.get("id", pack_id)).strip()
    dag_raw = raw.get("default_dag") or []
    dag = _validate_dag([str(x) for x in dag_raw], pack_id=pid)
    platforms = [str(p) for p in (raw.get("default_platforms") or [])]
    return PackConfig(
        id=pid,
        name=str(raw.get("name", pid)),
        description=str(raw.get("description", "")),
        default_dag=dag,
        default_platforms=platforms,
        samples_dir=str(raw.get("samples_dir", "samples")),
        verify=dict(raw.get("verify") or {}),
    )


def list_packs(root: Path) -> list[PackConfig]:
    base = _packs_root(root)
    if not base.is_dir():
        return []
    out: list[PackConfig] = []
    for child in sorted(base.iterdir()):
        if child.is_dir() and (child / "pack.yaml").is_file():
            out.append(load_pack(root, child.name))
    return out
