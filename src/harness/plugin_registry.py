"""十 Agent 插件注册表与统一 invoke 入口。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.agents.base import HarnessContext

AgentRunner = Callable[..., dict[str, Any]]

_REGISTRY: dict[str, tuple[AgentRunner, "PluginInfo"]] = {}


@dataclass(frozen=True)
class PluginInfo:
    agent_id: str
    version: str
    description: str
    status: str  # ready | stub


def register(
    agent_id: str,
    runner: AgentRunner,
    *,
    version: str = "1.0.0",
    description: str = "",
    status: str = "ready",
) -> None:
    _REGISTRY[agent_id] = (
        runner,
        PluginInfo(
            agent_id=agent_id,
            version=version,
            description=description,
            status=status,
        ),
    )


def get(agent_id: str) -> AgentRunner:
    entry = _REGISTRY.get(agent_id)
    if entry is None:
        raise KeyError(f"Unknown agent_id: {agent_id}")
    return entry[0]


def list_plugins() -> list[PluginInfo]:
    return [plugin_info for _aid, (_runner, plugin_info) in sorted(_REGISTRY.items(), key=lambda x: x[0])]


def invoke(
    agent_id: str,
    *,
    use_llm: bool,
    context: HarnessContext,
    llm_cfg: dict[str, Any],
    root: Path | None = None,
) -> dict[str, Any]:
    runner = get(agent_id)
    return runner(use_llm=use_llm, context=context, llm_cfg=llm_cfg, root=root)


def _register_all() -> None:
    from src.agents.a_agent import run_a_plugin
    from src.agents.c_agent import run_c_plugin
    from src.agents.d_agent import run_d_plugin
    from src.agents.e_agent import run_e_plugin
    from src.agents.f_agent import run_f_plugin
    from src.agents.m_agent import run_m_plugin
    from src.agents.n_agent import run_n_plugin
    from src.agents.p_agent import run_p_plugin
    from src.agents.s_agent import run_s_plugin
    from src.agents.u_agent import run_u_plugin

    register("D", run_d_plugin, description="数据运营 · 洞察与角度", status="ready")
    register("C", run_c_plugin, description="内容运营 · 多平台文案", status="ready")
    register("N", run_n_plugin, description="渠道运营 · 排期与标签", status="ready")
    register("U", run_u_plugin, description="用户运营 · 分群与留存", status="ready")
    register("A", run_a_plugin, description="活动运营 · 战役计划与ROI", status="ready")
    register("P", run_p_plugin, description="产品运营 · 功能洞察与迭代", status="ready")
    register("M", run_m_plugin, description="市场运营 · 定位与渠道组合", status="ready")
    register("F", run_f_plugin, description="流量运营 · 渠道评分与预算", status="ready")
    register("S", run_s_plugin, description="社群运营 · 社群动作与KOL", status="ready")
    register("E", run_e_plugin, description="交易运营 · 漏斗与CTA", status="ready")


_register_all()
