"""Agent 插件契约：每个 Agent = 领域计算 + LLM 推理 + 输出验证。

十个 Agent 分三类：
  Rule-first（规则优先）: D, N — 非 LLM 逻辑提供不可替代的领域价值
  LLM-augmented（LLM 增强）: U, C, A, F — LLM 主推理 + 领域规则校验
  Strategy-advisory（策略建议）: M, P, S, E — LLM 生成策略建议

每个 Agent 必须：
  1. 定义 input_schema（它消费什么）
  2. 定义 output_schema（它产出什么）
  3. 实现 validate(payload) → 非 LLM 的输出校验
  4. 实现 run() → Mock/LLM 双路径
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

AGENT_IDS: tuple[str, ...] = ("D", "U", "C", "A", "P", "M", "F", "N", "S", "E")

# ── Agent 分类 ──
RULE_FIRST = {"D", "N"}
LLM_AUGMENTED = {"U", "C", "A", "F"}
STRATEGY_ADVISORY = {"M", "P", "S", "E"}


class HarnessContext(dict):
    """Harness 注入的运行时上下文。Agent 只读。"""
    pass


class AgentPlugin(Protocol):
    agent_id: str
    version: str
    tier: str  # "rule_first" | "llm_augmented" | "strategy_advisory"

    def validate(self, payload: dict[str, Any]) -> list[str]:
        """非 LLM 输出校验。返回问题列表，空列表 = 通过。"""
        ...

    def run(
        self, *, use_llm: bool, context: dict[str, Any],
        llm_cfg: dict[str, Any], root: Path | None = None,
    ) -> dict[str, Any]:
        ...


def has_fallback(payload: dict[str, Any]) -> bool:
    fb = payload.get("_operai_fallback")
    return isinstance(fb, str) and bool(fb.strip())
