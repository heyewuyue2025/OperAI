"""Display labels used by Streamlit renderers.

LLM and rule-based agents use compact JSON keys internally. The UI should never
expose those implementation keys directly to operations users.
"""
from __future__ import annotations

from typing import Any


PLATFORM_LABELS = {
    "weibo": "微博",
    "wechat": "微信公众号",
    "xhs": "小红书",
    "bilibili": "哔哩哔哩",
    "douyin": "抖音",
    "kuaishou": "快手",
    "综合渠道": "综合渠道",
}

AGENT_LABELS = {
    "D": "材料洞察",
    "C": "内容生成",
    "N": "渠道排期",
    "U": "用户分层",
    "A": "活动结构",
    "P": "产品运营",
    "M": "市场策略",
    "F": "流量预算",
    "S": "社群运营",
    "E": "转化优化",
}

KEY_LABELS = {
    "phase": "阶段",
    "objective": "目标",
    "tasks": "动作",
    "owner_agent": "协作智能体",
    "owner agent": "协作智能体",
    "budget_hints": "预算提示",
    "budget_allocation": "预算分配",
    "roi_estimate": "ROI 预估",
    "summary": "摘要",
    "assumptions": "评估假设",
    "confidence": "置信度",
    "name": "人群",
    "description": "说明",
    "priority": "优先级",
    "segment": "人群",
    "action": "动作",
    "channel": "渠道",
    "suggestion": "建议",
    "percent_range": "预算区间",
    "percent range": "预算区间",
    "lifecycle_stage": "生命周期",
    "feature": "功能",
    "insight": "洞察",
    "metric_ref": "指标来源",
    "recommendation": "建议",
    "topic": "主题",
    "note": "说明",
    "role": "角色",
    "weight": "权重",
    "profile": "对象",
    "approach": "合作方式",
    "scenario": "场景",
    "script": "话术",
    "platform": "平台",
    "window": "时间窗",
    "reason": "理由",
    "text": "内容",
    "step": "环节",
    "dropoff_risk": "流失风险",
    "offer": "方案",
    "constraint": "约束",
    "percent": "占比",
    "rationale": "判断依据",
    "score": "评分",
    "timing": "时间",
    "goal": "目标",
    "positioning": "定位",
    "campaign_plan": "活动阶段",
    "channel_scores": "渠道评分",
    "conversion_hints": "转化建议",
    "community_actions": "社群动作",
    "kol_hints": "KOL 与共创",
    "engagement_scripts": "互动话术",
    "feature_insights": "功能洞察",
    "ux_signals": "体验信号",
    "iteration_hints": "迭代建议",
    "competitive_notes": "竞品与机会",
    "channel_mix": "渠道组合",
    "drafts": "平台内容",
    "title_variants": "备选标题",
    "short_video_script": "短视频脚本",
    "compliance_notes": "合规说明",
    "schedule_suggestions": "排期建议",
    "hashtags": "推荐标签",
    "segments": "用户分群",
    "retention_actions": "触达策略",
    "churn_risks": "流失风险",
    "funnel_steps": "转化漏斗",
    "promo_suggestions": "促销方案",
    "cta_variants": "CTA 变体",
}

VALUE_LABELS = {
    "high": "高",
    "medium": "中",
    "low": "低",
    "acquisition": "获取",
    "activation": "激活",
    "retention": "留存",
    "revenue": "变现",
    "referral": "推荐",
    "success": "成功",
    "failed": "失败",
    "pending": "待处理",
    "copy": "内容交付",
    "plan": "方案交付",
    "strategy": "策略交付",
    "experiment": "实验交付",
    "report": "报告交付",
    "playbook": "手册交付",
}


def label_key(key: Any) -> str:
    text = str(key).strip()
    normalized = text.replace("_", " ")
    return KEY_LABELS.get(text, KEY_LABELS.get(normalized, normalized))


def label_value(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(label_value(item) for item in value)
    if isinstance(value, dict):
        parts = [
            f"{label_key(k)}：{label_value(v)}"
            for k, v in value.items()
            if not str(k).startswith("_")
        ]
        return "；".join(parts)
    text = str(value).strip()
    if text in PLATFORM_LABELS:
        return PLATFORM_LABELS[text]
    if text in AGENT_LABELS:
        return f"{AGENT_LABELS[text]}（{text}）"
    return VALUE_LABELS.get(text, text)
