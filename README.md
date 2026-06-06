# OperAI Harness

面向企业运营团队的智能运营编排系统。

OperAI Harness 不是一个普通的 AI 聊天窗口，也不是单纯的文案生成器。它把企业运营任务拆解为可执行的 Skill 链路，由 Harness 引擎负责任务理解、能力匹配、上下文传递、运行档案、质量检验和交付导出，让运营工作从临时经验变成可复用、可复核、可沉淀的团队能力。

## 产品定位

企业运营团队每天面对的不是单一文案任务，而是一整套跨岗位、跨平台、跨审核标准的工作流：

- 内容运营要把素材转成多平台内容资产。
- 用户运营要做分层、触达、召回和留存。
- 活动运营要拆目标、预算、节奏、风险和执行动作。
- 渠道运营要安排分发、排期、预算和归因。
- 增长投放要做实验、转化路径和预算优化。
- 产品运营要整理反馈、功能信号和迭代优先级。
- 社群运营要维护互动机制、KOL 线索和社群动作。
- 市场策略要形成定位、竞品、传播和渠道组合判断。

OperAI Harness 的核心范式是：

```text
职能入口 -> Skill Registry -> Harness Run -> 质量检验 -> 运行档案 / 交付导出
```

## 核心能力

| 能力 | 说明 |
| --- | --- |
| 8 个职能入口 | 按运营岗位进入工作台，避免所有任务都被粗暴处理成社媒文案 |
| 10 个运营智能体 | 覆盖数据、内容、用户、活动、渠道、增长、市场、产品、社群、交易等运营判断 |
| 52 个可组合 Skill | 将公司级运营方法拆成可选择、可新增、可复核的能力单元 |
| Harness 编排引擎 | 自动选择 Skill、安排顺序、传递上下文、生成运行计划 |
| 质量检验 | 检查证据覆盖、风险边界、平台适配和交付完整度 |
| Skill Studio | 预留用户新增自定义 Skill 的入口 |
| API 配置面板 | 支持在网页中配置 OpenAI-compatible 模型服务 |
| 比赛展示材料 | 内置 5 分钟路演 PPT 和讲稿，便于展示产品叙事 |

## 页面入口

项目包含两个本地服务：

- 产品首页：`http://127.0.0.1:8080`
- Harness 工作台：`http://127.0.0.1:8501`

首页由 `frontend/` 静态页面提供，工作台由 Streamlit 提供。

## 快速开始

### 1. 安装依赖

```powershell
cd operai-mvp
pip install -r requirements.txt
```

如需使用锁定版本：

```powershell
pip install -r requirements.lock
```

### 2. 配置环境变量

复制示例配置：

```powershell
Copy-Item .env.example .env
```

`.env` 中可配置：

```env
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-pro
OPERAI_MOCK=1
```

说明：

- 不填写 `OPENAI_API_KEY` 时，系统会自动走 Mock / 规则路径，适合离线演示。
- 填写 `OPENAI_API_KEY` 后，会调用 OpenAI-compatible 接口。
- `OPERAI_MOCK=1` 可强制使用本地 Mock。
- 请不要把真实 `.env` 提交到 GitHub。

### 3. 启动首页与工作台

推荐一键启动：

```powershell
.\start.ps1
```

也可以手动启动两个终端：

```powershell
# 终端 1：Streamlit 工作台
python -m streamlit run app.py

# 终端 2：品牌首页
python serve.py
```

## 测试

```powershell
$env:OPERAI_MOCK="1"
python -m pytest -q
```

当前测试覆盖：

- Agent 输出契约
- Harness DAG 执行
- Skill Registry
- 角色交付物模型
- 中文标签显示
- 渲染布局兜底
- 敏感词与质量检验
- Markdown / Word 导出

## 目录结构

```text
operai-mvp/
├─ app.py                         # Streamlit Harness 工作台
├─ serve.py                       # 静态首页服务
├─ start.ps1                      # Windows 一键启动脚本
├─ config.yaml                    # 运行时配置
├─ frontend/                      # 产品首页与视觉系统
├─ src/
│  ├─ agents/                     # 10 个运营智能体
│  ├─ harness/                    # Skill Registry、DAG Runner、质量检验
│  ├─ storage/                    # 本地存储
│  ├─ role_deliverables.py        # 8 职能交付物模型
│  ├─ render_output.py            # 输出结果渲染
│  ├─ display_labels.py           # 内部字段中文化
│  └─ voice_styles.py             # 50 个表达风格预设
├─ tests/                         # 自动化测试
├─ docs/                          # 设计与实现文档
├─ packs/                         # 兼容层 Pack 配置
└─ outputs/                       # 比赛展示 PPT 与讲稿
```

## 关键模块

### Harness + Skill

- `src/harness/skill_registry.py`：内置 52 个运营 Skill，支持推荐与自定义 Skill 保存。
- `src/role_deliverables.py`：定义 8 个职能入口及其默认交付物。
- `src/harness/dag_runner.py`：顺序执行智能体插件，并注入上游上下文。
- `src/harness/verify_gate.py`：质量检验与风险复核。

### Agent 集群

`src/agents/` 中包含 10 个运营智能体：

- D：数据与材料洞察
- C：内容运营
- U：用户运营
- A：活动运营
- N：渠道运营
- F：流量 / 增长
- M：市场策略
- P：产品运营
- S：社群运营
- E：交易运营

### 前端体验

- `frontend/index.html`：产品首页。
- `frontend/styles.css`：首页视觉系统。
- `frontend/streamlit-theme.css`：Streamlit 工作台深度美化样式。
- `frontend/main.js`：滚动、鼠标与页面动效。

## API 与模型配置

OperAI 使用 OpenAI-compatible 协议。你可以接入 DeepSeek、OpenAI 或其他兼容服务。

基础配置：

```env
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-pro
```

工作台的「运行设置」页也提供 API 信息配置入口，便于演示时临时切换模型服务。

## 比赛展示材料

配套路演材料位于：

```text
outputs/manual-20260606-operai-competition/presentations/operai-harness-pitch/output/
├─ OperAI-Harness-比赛展示版.pptx
└─ OperAI-Harness-比赛展示版-讲稿.md
```

这套材料按 5 分钟比赛展示设计，覆盖：

1. 运营团队痛点
2. OperAI 产品定位
3. Harness 编排机制
4. 8 职能 / 10 智能体 / 52 Skill
5. Demo 路径
6. 技术架构
7. 商业化路径

## 开源安全说明

本仓库不会提交：

- `.env`
- 本地数据库 `data/operai.sqlite3`
- 运行日志 `data/logs/`
- Python 缓存 `__pycache__/`
- Pytest 缓存 `.pytest_cache/`
- Streamlit 本地密钥 `.streamlit/secrets.toml`

如果你 fork 或二次开发，请确认不要把真实 API Key、用户数据、运行日志上传到公开仓库。

## 许可证

本项目使用 MIT License 开源。

