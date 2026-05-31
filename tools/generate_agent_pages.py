from __future__ import annotations

from pathlib import Path


AGENTS = {
    "d": {
        "code": "D",
        "name": "数据运营",
        "tier": "数据底座",
        "role": "把原始运营素材转为可验证指标、洞察、角度与风险信号。",
        "input": "活动说明、数据摘要、舆情材料、平台反馈、销售或转化数字。",
        "output": "insights、angles、risk_flags、evidence_spans、结构化 metrics。",
        "verify": "证据摘录必须来自原文；风险规则扫描承诺收益、夸大表述、敏感信息。",
        "example": "原始素材中的 36 小时续航、35dB 降噪会被提取为指标，并进入下游文案约束。",
        "upstream": "原始素材",
        "downstream": "C / U / A / F",
    },
    "u": {
        "code": "U",
        "name": "用户运营",
        "tier": "模型增强",
        "role": "把用户行为信号整理成分群、生命周期、流失风险与触达策略。",
        "input": "用户规模、复购、活跃、留存、反馈、渠道来源。",
        "output": "segments、lifecycle、churn_risks、retention_actions。",
        "verify": "分群必须有指标依据；流失预警不能脱离样本范围。",
        "example": "把近 30 天活跃下降用户归为需唤醒人群，并生成触达建议。",
        "upstream": "D 指标",
        "downstream": "C / S / E",
    },
    "c": {
        "code": "C",
        "name": "内容运营",
        "tier": "模型增强",
        "role": "把洞察转换成多平台文案、标题变体、短视频口播与合规注记。",
        "input": "D-Agent 洞察、风险信号、品牌调性、目标平台。",
        "output": "drafts、title_variants、short_video_script、compliance_notes。",
        "verify": "平台字数、禁用词、金融风险提示、跨平台核心数字一致性。",
        "example": "同一产品卖点会分别生成微博扩散、小红书种草、公众号深度叙事。",
        "upstream": "D / U / M",
        "downstream": "N / S / E",
    },
    "a": {
        "code": "A",
        "name": "活动运营",
        "tier": "模型增强",
        "role": "把目标、预算、节奏和资源组织成可执行战役档案。",
        "input": "活动目标、预算区间、时间窗口、资源约束、目标人群。",
        "output": "campaign_structure、timeline、budget_hints、roi_estimate、task_breakdown。",
        "verify": "预算分配不得超过总额；ROI 估算需暴露假设。",
        "example": "校园音乐节会被拆成预热、招募、现场、复盘四个阶段。",
        "upstream": "D / U / M",
        "downstream": "C / N / F",
    },
    "n": {
        "code": "N",
        "name": "渠道运营",
        "tier": "规则优先",
        "role": "把内容草案转换成平台排期、标签策略、首评引导和冲突检测。",
        "input": "C-Agent 文案、目标平台、平台规则、发布时间窗口。",
        "output": "schedule_suggestions、hashtags、platform_notes、first_comment_suggestions。",
        "verify": "同平台排期不能重复；标签数量需要精简；平台规则优先于模型建议。",
        "example": "微博安排互动高峰，小红书安排社区活跃窗口，公众号安排长阅读窗口。",
        "upstream": "C",
        "downstream": "导出库",
    },
    "f": {
        "code": "F",
        "name": "流量运营",
        "tier": "模型增强",
        "role": "把渠道表现整理成评分、预算分配、CAC 优化和转化路径建议。",
        "input": "渠道成本、曝光、点击、转化、客单价、历史表现。",
        "output": "channel_scores、budget_split、cac_notes、conversion_findings。",
        "verify": "预算归一化必须等于总额；评分维度需可解释。",
        "example": "对微博、小红书、公众号按转化、成本、匹配度分配投放预算。",
        "upstream": "D / A",
        "downstream": "N / E",
    },
    "m": {
        "code": "M",
        "name": "市场运营",
        "tier": "策略研判",
        "role": "把品牌定位、竞品、趋势和渠道组合整理成市场判断档案。",
        "input": "品牌信息、竞品材料、市场趋势、目标客群、传播目标。",
        "output": "positioning、competitor_notes、channel_mix、trend_insights。",
        "verify": "竞品判断需区分事实与推断；定位建议必须回到输入材料。",
        "example": "把新品上市材料转为差异化定位和渠道组合建议。",
        "upstream": "原始素材 / D",
        "downstream": "A / C / F",
    },
    "p": {
        "code": "P",
        "name": "产品运营",
        "tier": "策略研判",
        "role": "把功能数据和用户反馈整理成体验问题、归因和迭代优先级。",
        "input": "功能使用数据、用户评论、客服反馈、转化漏斗。",
        "output": "feature_findings、feedback_clusters、priority_queue、experiment_suggestions。",
        "verify": "优先级需要说明影响面、成本和证据来源。",
        "example": "把耳压感、续航、佩戴稳定性反馈整理成下一轮优化建议。",
        "upstream": "D / U",
        "downstream": "C / A",
    },
    "s": {
        "code": "S",
        "name": "社群运营",
        "tier": "策略研判",
        "role": "把社群语境整理成互动话术、KOL 线索、活动玩法和情绪监测。",
        "input": "社群聊天片段、评论区反馈、KOL 列表、活动目标。",
        "output": "conversation_prompts、kol_matches、community_actions、sentiment_notes。",
        "verify": "话术不能冒充用户真实评价；KOL 匹配需说明理由。",
        "example": "把用户评论中的疑虑转为社群答疑脚本和互动问题。",
        "upstream": "U / C",
        "downstream": "N / E",
    },
    "e": {
        "code": "E",
        "name": "交易运营",
        "tier": "策略研判",
        "role": "把转化漏斗整理成促销机制、CTA、商品页优化和 GMV 动作。",
        "input": "流量来源、点击、加购、支付、客单价、库存和活动约束。",
        "output": "funnel_findings、promotion_plan、cta_variants、gmv_actions。",
        "verify": "促销建议不能承诺收益；CTA 需匹配平台和客群。",
        "example": "把加购未支付人群转为限时权益、客服跟进和页面 CTA 优化。",
        "upstream": "F / S / C",
        "downstream": "导出库",
    },
}


def render_page(slug: str, agent: dict[str, str]) -> str:
    nav = "".join(f'<a href="{key}-agent.html">{item["code"]}</a>' for key, item in AGENTS.items())
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{agent["code"]}-Agent · {agent["name"]} — OperAI Archive</title>
<link rel="stylesheet" href="styles.css" />
</head>
<body>
<header class="nav">
  <a class="nav-brand" href="index.html">OperAI 档案馆</a>
  <nav class="nav-links" aria-label="智能体索引">{nav}</nav>
  <a class="btn btn-primary btn-sm" href="http://127.0.0.1:8501" data-workbench>打开档案台</a>
</header>

<main>
  <section class="agent-file-hero">
    <div class="file-card reveal visible">
      <p class="file-meta">智能体档案 / {agent["code"]} / {agent["tier"]}</p>
      <div class="agent-code">{agent["code"]}</div>
      <span class="stamp">就绪</span>
    </div>
    <div class="reveal visible delay-1">
      <p class="eyebrow">运营情报工具</p>
      <h1 class="agent-title">{agent["name"]}<br>Agent</h1>
      <p class="hero-desc">{agent["role"]}</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="http://127.0.0.1:8501" data-workbench>在档案台运行</a>
        <a class="btn" href="index.html#agents">返回索引</a>
      </div>
    </div>
  </section>

  <div class="agent-layout">
    <aside class="side-index">
      <a href="#role">01 职责</a>
      <a href="#input">02 输入台账</a>
      <a href="#output">03 输出台账</a>
      <a href="#verify">04 校验规则</a>
      <a href="#chain">05 关联链路</a>
    </aside>

    <section class="agent-sections">
      <article class="dossier-panel reveal" id="role">
        <p class="section-kicker">01 / 档案职责</p>
        <h2 class="section-title" style="font-size:var(--text-2xl);">研究职责</h2>
        <p>{agent["role"]}</p>
      </article>

      <article class="dossier-panel reveal" id="input">
        <p class="section-kicker">02 / 输入台账</p>
        <table class="ledger-table">
          <tr><th>接收素材</th><td>{agent["input"]}</td></tr>
          <tr><th>上游</th><td>{agent["upstream"]}</td></tr>
        </table>
      </article>

      <article class="dossier-panel reveal" id="output">
        <p class="section-kicker">03 / 输出台账</p>
        <table class="ledger-table">
          <tr><th>结构化输出</th><td>{agent["output"]}</td></tr>
          <tr><th>示例档案</th><td>{agent["example"]}</td></tr>
        </table>
      </article>

      <article class="evidence-panel reveal" id="verify">
        <div class="trace-list">
          <div class="trace-node hot">校验规则</div>
          <div class="trace-node">{agent["verify"]}</div>
          <div class="trace-node">只有输出通过档案检查后，状态章才会点亮。</div>
        </div>
      </article>

      <article class="dossier-panel reveal" id="chain">
        <p class="section-kicker">05 / 关联链路</p>
        <table class="ledger-table">
          <tr><th>上游</th><td>{agent["upstream"]}</td></tr>
          <tr><th>下游</th><td>{agent["downstream"]}</td></tr>
          <tr><th>归档动作</th><td>打开档案台，创建任务案卷，运行该 Agent，再审阅运行档案和证据链。</td></tr>
        </table>
      </article>
    </section>
  </div>
</main>

<footer>
  <span>智能体档案 / {agent["code"]} / {agent["name"]}</span>
  <span>OperAI Archive OS</span>
</footer>
<script src="main.js"></script>
</body>
</html>
"""


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "frontend"
    for slug, agent in AGENTS.items():
        (root / f"{slug}-agent.html").write_text(render_page(slug, agent), encoding="utf-8")


if __name__ == "__main__":
    main()
