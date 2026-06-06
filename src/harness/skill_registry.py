"""Product-facing Skill Registry for the OperAI Harness Engine.

Skills are smaller operational capabilities that the harness can select,
sequence, evaluate, and expose to users. They are intentionally separate from
legacy pack wording so the product can grow beyond fixed job chains.
"""
from __future__ import annotations

import json
import re
from hashlib import sha1
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SkillSpec:
    id: str
    name: str
    category: str
    description: str
    inputs: list[str]
    outputs: list[str]
    checks: list[str]
    keywords: list[str]
    runner: str = ""
    source: str = "builtin"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SkillSpec":
        return cls(
            id=_normalize_id(str(raw.get("id", ""))),
            name=str(raw.get("name", "")).strip(),
            category=str(raw.get("category", "自定义")).strip() or "自定义",
            description=str(raw.get("description", "")).strip(),
            inputs=[str(x).strip() for x in raw.get("inputs", []) if str(x).strip()],
            outputs=[str(x).strip() for x in raw.get("outputs", []) if str(x).strip()],
            checks=[str(x).strip() for x in raw.get("checks", []) if str(x).strip()],
            keywords=[str(x).strip().lower() for x in raw.get("keywords", []) if str(x).strip()],
            runner=str(raw.get("runner", "")).strip().upper(),
            source=str(raw.get("source", "custom")).strip() or "custom",
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


BUILTIN_SKILLS: tuple[SkillSpec, ...] = (
    SkillSpec(
        id="material_intake",
        name="任务材料结构化",
        category="Harness 输入",
        description="把活动说明、产品卖点、用户反馈和平台数据整理成可执行任务 brief。",
        inputs=["原始素材", "业务目标", "平台范围"],
        outputs=["任务 brief", "信息缺口", "执行边界"],
        checks=["必须保留原始事实", "必须指出缺失信息"],
        keywords=["素材", "任务", "brief", "活动说明", "产品卖点", "输入"],
        runner="D",
    ),
    SkillSpec(
        id="evidence_extraction",
        name="证据摘录",
        category="证据链",
        description="从材料中抽取指标、事实、用户原话和可引用证据。",
        inputs=["原始素材", "用户反馈", "业务数据"],
        outputs=["事实摘录", "指标清单", "证据片段"],
        checks=["数字必须来自输入", "主张必须能回溯"],
        keywords=["证据", "指标", "数据", "事实", "摘录", "引用"],
        runner="D",
    ),
    SkillSpec(
        id="feedback_synthesis",
        name="用户反馈归因",
        category="用户增长",
        description="把评论、客服记录和调研反馈归类为需求、阻力和机会点。",
        inputs=["用户评论", "客服反馈", "调研记录"],
        outputs=["反馈分类", "高频问题", "机会判断"],
        checks=["不能把单条反馈当成全局结论", "必须区分事实和推断"],
        keywords=["用户", "反馈", "评论", "客服", "归因", "痛点", "需求"],
        runner="P",
    ),
    SkillSpec(
        id="audience_segmentation",
        name="人群分层",
        category="用户增长",
        description="把目标用户拆成可触达、可沟通、可复盘的人群层级。",
        inputs=["用户画像", "行为数据", "转化阶段"],
        outputs=["人群分层", "触达策略", "复盘指标"],
        checks=["每个人群必须有动作", "每个动作必须有指标"],
        keywords=["人群", "用户", "分层", "召回", "留存", "生命周期"],
        runner="U",
    ),
    SkillSpec(
        id="positioning_brief",
        name="市场定位简报",
        category="策略判断",
        description="把品牌、竞品和趋势材料整理成可用于运营决策的定位判断。",
        inputs=["品牌信息", "竞品材料", "市场趋势"],
        outputs=["定位判断", "差异化卖点", "传播机会"],
        checks=["必须说明竞争参照", "不能只输出抽象口号"],
        keywords=["市场", "定位", "竞品", "趋势", "品牌", "差异化"],
        runner="M",
    ),
    SkillSpec(
        id="campaign_architecture",
        name="活动结构设计",
        category="活动运营",
        description="把目标、预算、资源和节奏组织成可执行活动结构。",
        inputs=["活动目标", "时间窗口", "预算资源"],
        outputs=["活动阶段", "任务拆解", "风险提醒"],
        checks=["阶段必须有动作", "资源约束必须被体现"],
        keywords=["活动", "战役", "预算", "节奏", "玩法", "roi"],
        runner="A",
    ),
    SkillSpec(
        id="platform_copywriting",
        name="平台内容生成",
        category="内容生产",
        description="生成适配微博、公众号、小红书、抖音等平台的内容草案。",
        inputs=["任务 brief", "品牌语气", "目标平台"],
        outputs=["平台文案", "标题备选", "口播草案"],
        checks=["文案必须贴合平台", "必须保留核心卖点"],
        keywords=["文案", "内容", "小红书", "公众号", "微博", "抖音", "标题"],
        runner="C",
    ),
    SkillSpec(
        id="style_adaptation",
        name="表达口径适配",
        category="内容生产",
        description="把同一方案改写成不同品牌语气、平台风格和用户语境。",
        inputs=["原始文案", "品牌语气", "目标受众"],
        outputs=["改写版本", "语气说明", "禁用表达"],
        checks=["不能改变事实", "必须说明改写策略"],
        keywords=["改写", "语气", "口径", "风格", "表达", "品牌"],
        runner="C",
    ),
    SkillSpec(
        id="channel_calendar",
        name="渠道排期",
        category="发布编排",
        description="把内容草案安排到具体平台、时间窗口、标签和发布节奏。",
        inputs=["内容草案", "目标平台", "时间限制"],
        outputs=["发布排期", "平台标签", "发布注意事项"],
        checks=["每个平台至少一个动作", "排期必须可执行"],
        keywords=["排期", "渠道", "平台", "发布", "标签", "时间"],
        runner="N",
    ),
    SkillSpec(
        id="traffic_budgeting",
        name="流量预算建议",
        category="增长投放",
        description="根据渠道表现和目标转化给出预算分配与优化建议。",
        inputs=["渠道数据", "转化目标", "预算约束"],
        outputs=["渠道评分", "预算建议", "转化优化点"],
        checks=["建议必须对应指标", "不能超出预算约束"],
        keywords=["流量", "投放", "预算", "渠道评分", "转化", "cac"],
        runner="F",
    ),
    SkillSpec(
        id="community_activation",
        name="社群互动设计",
        category="社群运营",
        description="把社群语境转成互动话术、玩法动作和 KOL 线索。",
        inputs=["社群材料", "互动目标", "用户画像"],
        outputs=["互动话术", "社群动作", "KOL 线索"],
        checks=["话术必须自然", "动作必须能被运营执行"],
        keywords=["社群", "互动", "kol", "话术", "用户群", "评论区"],
        runner="S",
    ),
    SkillSpec(
        id="conversion_cta",
        name="转化 CTA 优化",
        category="交易转化",
        description="把转化漏斗问题转成促销、CTA 和商品页优化动作。",
        inputs=["漏斗数据", "商品信息", "促销约束"],
        outputs=["漏斗诊断", "CTA 变体", "促销建议"],
        checks=["CTA 必须和用户阻力对应", "促销不能突破约束"],
        keywords=["转化", "cta", "交易", "漏斗", "促销", "商品"],
        runner="E",
    ),
    SkillSpec(
        id="seo_keyword_map",
        name="SEO 关键词地图",
        category="搜索增长",
        description="把业务主题拆成核心词、长尾词、搜索意图和内容机会。",
        inputs=["业务主题", "目标用户", "竞品页面"],
        outputs=["关键词分组", "搜索意图", "内容机会"],
        checks=["必须区分信息型和转化型意图", "关键词必须能对应内容动作"],
        keywords=["seo", "关键词", "搜索", "长尾词", "内容机会"],
        runner="M",
    ),
    SkillSpec(
        id="seo_content_brief",
        name="SEO 内容简报",
        category="搜索增长",
        description="把关键词和用户意图转成可写作的 SEO 内容 brief。",
        inputs=["关键词地图", "目标读者", "产品卖点"],
        outputs=["文章结构", "标题建议", "内链建议"],
        checks=["结构必须覆盖搜索意图", "不能堆砌关键词"],
        keywords=["seo", "文章", "内容 brief", "标题", "内链"],
        runner="C",
    ),
    SkillSpec(
        id="social_calendar",
        name="社媒内容日历",
        category="社媒运营",
        description="把传播目标拆成连续发布主题、内容形式和互动节点。",
        inputs=["传播目标", "平台列表", "活动周期"],
        outputs=["内容日历", "互动节点", "素材需求"],
        checks=["每个节点必须有平台和目标", "内容形式不能单一"],
        keywords=["社媒", "日历", "内容排期", "微博", "小红书", "抖音"],
        runner="N",
    ),
    SkillSpec(
        id="short_video_script",
        name="短视频脚本",
        category="视频运营",
        description="把卖点、场景和用户痛点转成短视频分镜与口播脚本。",
        inputs=["产品卖点", "目标受众", "视频平台"],
        outputs=["开场 Hook", "分镜脚本", "口播文案"],
        checks=["前三秒必须有 Hook", "脚本必须能实际拍摄"],
        keywords=["短视频", "脚本", "口播", "分镜", "抖音", "视频号"],
        runner="C",
    ),
    SkillSpec(
        id="email_campaign",
        name="邮件活动策划",
        category="邮件营销",
        description="把活动目标和用户阶段转成邮件主题、正文和 CTA。",
        inputs=["用户阶段", "活动目标", "产品信息"],
        outputs=["邮件主题", "邮件正文", "CTA"],
        checks=["主题必须清晰", "CTA 必须和用户阶段一致"],
        keywords=["邮件", "newsletter", "edm", "主题", "cta"],
        runner="C",
    ),
    SkillSpec(
        id="lifecycle_journey",
        name="生命周期旅程",
        category="CRM 运营",
        description="把用户从新客、活跃、沉默到流失的阶段设计成运营旅程。",
        inputs=["用户阶段", "行为数据", "业务目标"],
        outputs=["旅程地图", "触点策略", "阶段指标"],
        checks=["每个阶段必须有触点", "必须定义转段指标"],
        keywords=["生命周期", "crm", "旅程", "新客", "沉默", "流失"],
        runner="U",
    ),
    SkillSpec(
        id="onboarding_flow",
        name="新用户激活流程",
        category="用户增长",
        description="设计新用户首次体验、教育触达和激活动作。",
        inputs=["产品功能", "新用户画像", "激活定义"],
        outputs=["激活路径", "教育内容", "关键指标"],
        checks=["激活定义必须明确", "动作必须能被产品或运营执行"],
        keywords=["新用户", "激活", "onboarding", "教育", "首日"],
        runner="U",
    ),
    SkillSpec(
        id="retention_winback",
        name="流失召回策略",
        category="用户增长",
        description="根据流失信号、人群价值和触达渠道生成召回方案。",
        inputs=["流失用户", "用户价值", "触达渠道"],
        outputs=["召回分层", "触达话术", "复盘指标"],
        checks=["不能过度打扰", "必须区分高低价值用户"],
        keywords=["流失", "召回", "留存", "沉默用户", "复购"],
        runner="U",
    ),
    SkillSpec(
        id="referral_program",
        name="推荐裂变方案",
        category="增长机制",
        description="设计用户推荐、奖励机制、传播路径和反作弊边界。",
        inputs=["目标用户", "奖励资源", "传播渠道"],
        outputs=["推荐机制", "奖励规则", "风险边界"],
        checks=["奖励必须可承受", "必须考虑作弊风险"],
        keywords=["推荐", "裂变", "邀请", "奖励", "增长"],
        runner="F",
    ),
    SkillSpec(
        id="paid_media_brief",
        name="付费投放 Brief",
        category="增长投放",
        description="把投放目标转成受众、渠道、预算、素材和转化追踪要求。",
        inputs=["投放目标", "预算", "目标人群"],
        outputs=["投放 brief", "渠道建议", "素材清单"],
        checks=["预算必须分配到渠道", "必须定义转化事件"],
        keywords=["投放", "paid", "广告", "预算", "素材"],
        runner="F",
    ),
    SkillSpec(
        id="ad_creative_testing",
        name="广告素材测试",
        category="增长实验",
        description="设计广告素材变量、测试组合和判断标准。",
        inputs=["素材方向", "目标人群", "投放数据"],
        outputs=["测试矩阵", "胜出标准", "迭代建议"],
        checks=["变量不能混杂", "必须定义判断周期"],
        keywords=["广告", "素材", "测试", "创意", "ab"],
        runner="F",
    ),
    SkillSpec(
        id="landing_page_cro",
        name="落地页转化优化",
        category="转化优化",
        description="检查落地页结构、卖点、CTA、信任元素和转化阻力。",
        inputs=["落地页内容", "流量来源", "转化目标"],
        outputs=["问题清单", "改版建议", "实验假设"],
        checks=["建议必须对应转化阻力", "不能只改视觉不改路径"],
        keywords=["落地页", "cro", "转化", "cta", "表单"],
        runner="E",
    ),
    SkillSpec(
        id="ab_test_design",
        name="A/B 实验设计",
        category="增长实验",
        description="把优化假设转成实验变量、样本、指标和停止规则。",
        inputs=["实验假设", "目标指标", "流量规模"],
        outputs=["实验方案", "指标定义", "停止规则"],
        checks=["只能测试清晰变量", "必须说明成功标准"],
        keywords=["ab", "实验", "测试", "假设", "样本"],
        runner="D",
    ),
    SkillSpec(
        id="growth_loop_design",
        name="增长飞轮设计",
        category="增长机制",
        description="把获客、激活、传播和复购设计成可循环的增长机制。",
        inputs=["产品机制", "用户行为", "传播渠道"],
        outputs=["增长循环", "关键杠杆", "断点风险"],
        checks=["循环必须闭合", "必须指出最脆弱环节"],
        keywords=["增长飞轮", "growth loop", "循环", "病毒", "传播"],
        runner="M",
    ),
    SkillSpec(
        id="north_star_metric",
        name="北极星指标定义",
        category="数据分析",
        description="定义北极星指标、输入指标和监控口径。",
        inputs=["业务模式", "用户价值", "现有指标"],
        outputs=["北极星指标", "输入指标树", "监控口径"],
        checks=["指标必须反映用户价值", "不能只选收入结果指标"],
        keywords=["北极星", "指标", "metric", "数据", "增长"],
        runner="D",
    ),
    SkillSpec(
        id="attribution_plan",
        name="归因追踪方案",
        category="数据分析",
        description="设计渠道归因、UTM 规范、事件口径和看板需求。",
        inputs=["渠道列表", "转化路径", "现有数据"],
        outputs=["归因方案", "UTM 规范", "事件口径"],
        checks=["必须说明归因窗口", "必须处理多触点路径"],
        keywords=["归因", "utm", "渠道", "埋点", "tracking", "看板", "付费投放"],
        runner="D",
    ),
    SkillSpec(
        id="dashboard_kpi",
        name="运营看板指标",
        category="数据分析",
        description="把业务目标转成运营看板指标、维度和预警规则。",
        inputs=["业务目标", "数据来源", "运营动作"],
        outputs=["指标看板", "维度拆解", "预警规则"],
        checks=["指标必须能驱动动作", "预警阈值必须有解释"],
        keywords=["看板", "kpi", "dashboard", "预警", "数据"],
        runner="D",
    ),
    SkillSpec(
        id="market_research_plan",
        name="市场调研计划",
        category="市场研究",
        description="设计用户访谈、问卷、竞品和渠道调研的问题框架。",
        inputs=["调研目标", "目标人群", "业务问题"],
        outputs=["调研问题", "样本计划", "分析框架"],
        checks=["问题不能诱导", "样本必须匹配目标人群"],
        keywords=["调研", "市场研究", "访谈", "问卷", "洞察"],
        runner="M",
    ),
    SkillSpec(
        id="competitive_battlecard",
        name="竞品作战卡",
        category="竞争情报",
        description="把竞品信息整理成卖点对比、风险回应和销售运营话术。",
        inputs=["竞品资料", "客户异议", "产品优势"],
        outputs=["对比表", "异议回应", "话术建议"],
        checks=["不能贬低竞品", "必须区分事实和判断"],
        keywords=["竞品", "battlecard", "竞争", "对比", "异议"],
        runner="M",
    ),
    SkillSpec(
        id="brand_voice_system",
        name="品牌表达系统",
        category="品牌管理",
        description="沉淀品牌语气、禁用表达、内容原则和示例句式。",
        inputs=["品牌定位", "历史内容", "受众画像"],
        outputs=["语气规范", "禁用表达", "示例句式"],
        checks=["规范必须可执行", "必须给出正反例"],
        keywords=["品牌", "语气", "口径", "voice", "规范"],
        runner="C",
    ),
    SkillSpec(
        id="pr_press_release",
        name="新闻稿草案",
        category="公关传播",
        description="把产品发布、活动或融资信息整理成新闻稿结构。",
        inputs=["新闻事实", "核心信息", "引用素材"],
        outputs=["新闻稿标题", "正文草案", "媒体要点"],
        checks=["新闻事实必须准确", "不能夸大未证实信息"],
        keywords=["公关", "新闻稿", "pr", "媒体", "发布"],
        runner="C",
    ),
    SkillSpec(
        id="media_outreach",
        name="媒体沟通清单",
        category="公关传播",
        description="为传播主题设计媒体分层、沟通角度和跟进节奏。",
        inputs=["传播主题", "目标媒体", "新闻价值"],
        outputs=["媒体分层", "沟通角度", "跟进节奏"],
        checks=["角度必须匹配媒体", "不能群发同一话术"],
        keywords=["媒体", "pr", "外联", "沟通", "传播"],
        runner="M",
    ),
    SkillSpec(
        id="event_webinar_plan",
        name="线上活动策划",
        category="活动运营",
        description="设计直播、 webinar、社群活动的主题、流程和转化动作。",
        inputs=["活动目标", "嘉宾资源", "目标人群"],
        outputs=["活动流程", "传播节奏", "转化动作"],
        checks=["流程必须有时间线", "必须有活动后跟进"],
        keywords=["直播", "webinar", "线上活动", "活动流程", "嘉宾"],
        runner="A",
    ),
    SkillSpec(
        id="offline_event_ops",
        name="线下活动执行",
        category="活动运营",
        description="把线下活动拆成物料、人员、流程、风险和复盘清单。",
        inputs=["活动主题", "场地信息", "人员安排"],
        outputs=["执行清单", "现场流程", "风险预案"],
        checks=["必须覆盖现场风险", "必须有负责人和时间点"],
        keywords=["线下活动", "物料", "现场", "执行", "复盘"],
        runner="A",
    ),
    SkillSpec(
        id="influencer_collaboration",
        name="达人合作方案",
        category="社媒运营",
        description="设计达人筛选、合作 brief、内容要求和效果复盘。",
        inputs=["达人名单", "产品卖点", "预算"],
        outputs=["达人筛选", "合作 brief", "复盘指标"],
        checks=["达人必须匹配受众", "必须定义内容交付标准"],
        keywords=["达人", "kol", "koc", "合作", "种草"],
        runner="S",
    ),
    SkillSpec(
        id="community_programming",
        name="社群栏目设计",
        category="社群运营",
        description="把社群目标转成固定栏目、互动机制和成员成长路径。",
        inputs=["社群目标", "成员画像", "资源约束"],
        outputs=["栏目设计", "互动机制", "成长路径"],
        checks=["栏目必须可持续", "互动不能只靠管理员单向输出"],
        keywords=["社群", "栏目", "会员", "互动", "用户运营"],
        runner="S",
    ),
    SkillSpec(
        id="customer_success_health",
        name="客户健康度运营",
        category="客户成功",
        description="为存量客户设计健康度指标、预警信号和跟进动作。",
        inputs=["客户行为", "使用数据", "续费目标"],
        outputs=["健康度指标", "风险预警", "跟进动作"],
        checks=["指标必须能提前预警", "动作必须分优先级"],
        keywords=["客户成功", "健康度", "续费", "风险", "存量"],
        runner="U",
    ),
    SkillSpec(
        id="voice_of_customer",
        name="客户之声分析",
        category="客户洞察",
        description="把 NPS、访谈、客服和社群反馈合成为客户洞察。",
        inputs=["NPS", "访谈记录", "客服反馈"],
        outputs=["主题洞察", "优先级", "行动建议"],
        checks=["必须保留代表性原话", "必须区分高频和高影响问题"],
        keywords=["voc", "客户之声", "nps", "访谈", "反馈"],
        runner="P",
    ),
    SkillSpec(
        id="pricing_packaging",
        name="定价与套餐建议",
        category="商业化运营",
        description="根据用户分层、价值感知和竞品价格给出套餐建议。",
        inputs=["用户分层", "竞品价格", "功能价值"],
        outputs=["套餐结构", "价格假设", "验证实验"],
        checks=["必须说明付费意愿假设", "必须给出验证方式"],
        keywords=["定价", "套餐", "pricing", "付费", "商业化"],
        runner="M",
    ),
    SkillSpec(
        id="partnership_comarketing",
        name="合作共创方案",
        category="合作运营",
        description="设计渠道合作、品牌联名和资源置换的共创方案。",
        inputs=["潜在伙伴", "资源清单", "共同目标"],
        outputs=["合作机制", "传播主题", "权益分配"],
        checks=["双方价值必须清晰", "必须说明执行边界"],
        keywords=["合作", "联名", "渠道", "共创", "资源置换"],
        runner="M",
    ),
    SkillSpec(
        id="abm_account_plan",
        name="重点客户运营计划",
        category="ABM 运营",
        description="为重点客户设计账户画像、触达路径和内容资产。",
        inputs=["目标账户", "关键人信息", "业务痛点"],
        outputs=["账户计划", "触达路径", "内容资产"],
        checks=["必须识别关键角色", "触达内容必须对应痛点"],
        keywords=["abm", "重点客户", "账户", "大客户", "触达"],
        runner="M",
    ),
    SkillSpec(
        id="lead_scoring",
        name="线索评分规则",
        category="RevOps",
        description="根据行为、属性和意向信号设计线索评分和分发规则。",
        inputs=["线索属性", "行为数据", "销售反馈"],
        outputs=["评分规则", "分发标准", "跟进建议"],
        checks=["评分必须可解释", "必须避免单一行为过度加权"],
        keywords=["线索", "评分", "lead scoring", "mql", "sql"],
        runner="D",
    ),
    SkillSpec(
        id="marketing_automation_nurture",
        name="自动化培育流程",
        category="营销自动化",
        description="设计线索培育、触发条件、内容节点和退出规则。",
        inputs=["线索阶段", "内容资产", "触发事件"],
        outputs=["自动化流程", "内容节点", "退出规则"],
        checks=["必须有停止条件", "不能对用户重复轰炸"],
        keywords=["自动化", "培育", "nurture", "触发", "crm"],
        runner="U",
    ),
    SkillSpec(
        id="crm_data_hygiene",
        name="CRM 数据清洗",
        category="RevOps",
        description="识别 CRM 数据缺失、重复、字段混乱和同步风险。",
        inputs=["CRM 字段", "线索数据", "销售反馈"],
        outputs=["数据问题", "字段规范", "修复优先级"],
        checks=["必须区分系统问题和人工录入问题", "必须给出字段标准"],
        keywords=["crm", "数据清洗", "字段", "重复", "线索"],
        runner="D",
    ),
    SkillSpec(
        id="ecommerce_cart_recovery",
        name="购物车挽回",
        category="电商运营",
        description="为加购未购用户设计挽回触达、优惠和复盘指标。",
        inputs=["加购数据", "商品信息", "优惠约束"],
        outputs=["挽回策略", "触达话术", "复盘指标"],
        checks=["优惠必须受控", "触达必须符合用户阶段"],
        keywords=["购物车", "电商", "加购", "挽回", "优惠"],
        runner="E",
    ),
    SkillSpec(
        id="merchandising_promo",
        name="商品促销排布",
        category="电商运营",
        description="设计商品组合、促销节奏、利益点和页面陈列建议。",
        inputs=["商品列表", "库存", "促销目标"],
        outputs=["商品组合", "促销节奏", "陈列建议"],
        checks=["不能忽略库存约束", "利益点必须清晰"],
        keywords=["商品", "促销", "电商", "库存", "陈列"],
        runner="E",
    ),
    SkillSpec(
        id="app_store_aso",
        name="应用商店 ASO",
        category="渠道运营",
        description="优化应用商店标题、关键词、截图文案和转化信息。",
        inputs=["应用信息", "竞品页面", "目标关键词"],
        outputs=["ASO 建议", "截图文案", "关键词优化"],
        checks=["关键词必须自然", "截图文案必须匹配功能价值"],
        keywords=["aso", "应用商店", "app", "关键词", "截图"],
        runner="N",
    ),
    SkillSpec(
        id="crisis_response",
        name="舆情应对方案",
        category="公关传播",
        description="把负面反馈、风险事实和回应边界整理成舆情应对方案。",
        inputs=["舆情材料", "事实核查", "回应边界"],
        outputs=["风险分级", "回应口径", "处置节奏"],
        checks=["必须先核实事实", "不能承诺未确认事项"],
        keywords=["舆情", "危机", "公关", "回应", "负面"],
        runner="M",
    ),
    SkillSpec(
        id="evidence_review",
        name="质量与证据复核",
        category="Harness 评估",
        description="检查方案的事实依据、平台适配、表达一致性和合规风险。",
        inputs=["任务 brief", "技能输出", "原始证据"],
        outputs=["质量评分", "风险项", "复核建议"],
        checks=["必须指出证据缺口", "必须给出可修复建议"],
        keywords=["复核", "校验", "质量", "证据", "合规", "风险", "敏感"],
        runner="D",
    ),
    SkillSpec(
        id="delivery_package",
        name="交付成稿",
        category="交付导出",
        description="把技能输出整理成可复核、可编辑、可提交的运营交付物。",
        inputs=["技能输出", "复核结果", "交付格式"],
        outputs=["交付文档", "摘要", "待确认事项"],
        checks=["必须保留待人工确认事项", "导出结构必须完整"],
        keywords=["交付", "导出", "文档", "方案", "复盘", "成稿"],
        runner="C",
    ),
)


def list_builtin_skills() -> list[SkillSpec]:
    return list(BUILTIN_SKILLS)


def list_skills(root: Path) -> list[SkillSpec]:
    custom = _load_custom_skills(root)
    merged: dict[str, SkillSpec] = {skill.id: skill for skill in BUILTIN_SKILLS}
    for skill in custom:
        merged[skill.id] = skill
    return sorted(merged.values(), key=lambda item: (item.category, item.name))


def plan_skills(task_text: str, *, root: Path | None = None, limit: int = 6) -> list[SkillSpec]:
    skills = list_skills(root) if root is not None else list_builtin_skills()
    text = task_text.lower()
    scored: list[tuple[int, SkillSpec]] = []
    for skill in skills:
        score = _score_skill(skill, text)
        if score > 0:
            scored.append((score, skill))
    if not scored:
        fallback_ids = ["material_intake", "evidence_extraction", "platform_copywriting", "evidence_review", "delivery_package"]
        return [skill for skill in skills if skill.id in fallback_ids][:limit]
    scored.sort(key=lambda item: (-item[0], item[1].category, item[1].name))
    return [skill for _score, skill in scored[:limit]]


def save_custom_skill(root: Path, skill: SkillSpec) -> None:
    _validate_skill(skill)
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    path = _custom_skill_path(root)
    skills = {item.id: item for item in _load_custom_skills(root)}
    skills[skill.id] = SkillSpec.from_dict({**skill.to_dict(), "source": "custom"})
    payload = [item.to_dict() for item in sorted(skills.values(), key=lambda item: item.id)]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_skill_from_form(
    *,
    name: str,
    category: str,
    description: str,
    inputs_text: str,
    outputs_text: str,
    checks_text: str,
    keywords_text: str,
    runner: str = "",
) -> SkillSpec:
    skill_id = _normalize_id(name)
    return SkillSpec(
        id=skill_id,
        name=name.strip(),
        category=category.strip() or "自定义",
        description=description.strip(),
        inputs=_split_lines(inputs_text),
        outputs=_split_lines(outputs_text),
        checks=_split_lines(checks_text),
        keywords=[item.lower() for item in _split_lines(keywords_text)],
        runner=runner.strip().upper(),
        source="custom",
    )


def _score_skill(skill: SkillSpec, text: str) -> int:
    fields = " ".join([skill.name, skill.category, skill.description, *skill.keywords]).lower()
    score = 0
    if skill.name.lower() in text:
        score += 8
    for phrase in [skill.category.lower(), *skill.keywords]:
        if phrase and phrase in text:
            score += 5
    for keyword in skill.keywords:
        if keyword and keyword in text:
            score += 3
    for token in re.findall(r"[\w\u4e00-\u9fff]+", text):
        if len(token) >= 2 and token in fields:
            score += 1
    return score


def _custom_skill_path(root: Path) -> Path:
    return root / "data" / "custom_skills.json"


def _load_custom_skills(root: Path) -> list[SkillSpec]:
    path = _custom_skill_path(root)
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []
    return [SkillSpec.from_dict(item) for item in raw if isinstance(item, dict)]


def _split_lines(value: str) -> list[str]:
    items: list[str] = []
    for line in value.replace("，", "\n").replace(",", "\n").splitlines():
        text = line.strip(" -\t")
        if text:
            items.append(text)
    return items


def _normalize_id(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        return "custom_skill"
    if re.search(r"[\u4e00-\u9fff]", text):
        return "custom_" + sha1(text.encode("utf-8")).hexdigest()[:8]
    return text


def _validate_skill(skill: SkillSpec) -> None:
    if not skill.id:
        raise ValueError("Skill id 不能为空")
    if not skill.name.strip():
        raise ValueError("Skill 名称不能为空")
    if not skill.inputs:
        raise ValueError("Skill 至少需要一个输入")
    if not skill.outputs:
        raise ValueError("Skill 至少需要一个输出")
