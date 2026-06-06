"""Preset voice-style words for the expression guideline field."""
from __future__ import annotations


VOICE_STYLE_PRESETS: tuple[str, ...] = (
    "克制可信",
    "清晰直接",
    "专业权威",
    "温和耐心",
    "年轻活泼",
    "轻松幽默",
    "真诚朴素",
    "理性分析",
    "简洁有力",
    "高级冷静",
    "亲切自然",
    "人情味",
    "行动导向",
    "数据驱动",
    "场景化",
    "故事感",
    "陪伴感",
    "顾问式",
    "专家型",
    "编辑部口吻",
    "实验室感",
    "商业杂志感",
    "产品经理视角",
    "用户同理心",
    "结果导向",
    "安全稳妥",
    "合规谨慎",
    "不夸张",
    "少营销腔",
    "少口号感",
    "有温度",
    "有节奏",
    "有记忆点",
    "结构清楚",
    "信息密度高",
    "适合管理层",
    "适合一线运营",
    "适合新用户",
    "适合老用户",
    "适合社群互动",
    "适合公域传播",
    "适合私域触达",
    "适合活动招募",
    "适合投放转化",
    "适合产品说明",
    "避免焦虑感",
    "避免绝对化",
    "避免生硬术语",
    "避免过度承诺",
    "保留品牌温度",
)


def merge_voice_styles(current: str, selected: list[str] | tuple[str, ...]) -> str:
    """Merge selected preset words into the expression guideline text."""
    valid = [item for item in selected if item in VOICE_STYLE_PRESETS]
    existing_lines = [
        line.strip()
        for line in (current or "").splitlines()
        if line.strip() and not line.strip().startswith("表达风格：")
    ]
    if valid:
        existing_lines.insert(0, f"表达风格：{'、'.join(valid)}")
    return "\n".join(existing_lines).strip()
