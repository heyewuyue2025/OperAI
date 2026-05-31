# OperAI 决赛 MVP（轻量全栈骨架）

## 安装与运行

1. Python **3.11+**（推荐 3.11 或 3.12）。
2. 进入本目录 `operai-mvp`。

**Windows PowerShell：**

```powershell
Set-Location 你的路径\operai-mvp
pip install -r requirements.txt
Copy-Item .env.example .env
```

**可复现安装（答辩机 / 录屏机）：**

```powershell
pip install -r requirements.lock
```

**干净环境自检（安装 + pytest）：**

```powershell
.\scripts\verify_env.ps1
```

**CMD：**

```bat
cd /d 你的路径\operai-mvp
pip install -r requirements.txt
copy .env.example .env
```

3. 编辑 `.env`：若填写 `OPENAI_API_KEY`，则 D/C/N 将调用云端模型（OpenAI 兼容接口）；留空则 **自动 Mock**，适合断网录屏。强制 Mock 可设 `OPERAI_MOCK=1`。
4. **推荐：品牌首页 + 工作台（双进程）**

```powershell
# 一键启动（Windows）
.\start.ps1

# 或手动开两个终端：
# 终端 1 — 决赛 Demo 工作台
streamlit run app.py

# 终端 2 — 你设计的项目首页（frontend/）
python serve.py
```

- 落地页：**http://127.0.0.1:8080**（Hero 区展示 D/C/N 决赛能力）
- 工作台：**http://127.0.0.1:8501**
- 首页按钮或 **http://127.0.0.1:8080/app** 会 302 跳转到工作台（需已启动 Streamlit）

仅跑工作台时：`streamlit run app.py` 即可。

### 依赖说明

- `requirements.txt`：`streamlit>=1.32,<1.40`（避免部分环境下 starlette/gzip 报错）。
- `requirements.lock`：冻结版本，便于 NFR 可复现；更新方法见文件头注释。

## 自动化测试

在项目根目录 `operai-mvp` 下执行（强制走 Mock，无需 Key）：

```powershell
$env:OPERAI_MOCK="1"
Set-Location 你的路径\operai-mvp
python -m pytest -q
```

（`tests/conftest.py` 已把项目根加入 `sys.path`，无需额外配置 `PYTHONPATH`。）

## 配置

- `config.yaml`：`paths.sqlite` / `paths.logs_dir`、`demo_mode`、`llm`、`harness.default_pack_id` / `harness.use_dag_runner`。
- `config/sensitive_words.txt`：敏感词表；可在 **设置** 页编辑并写回文件或仅本会话生效。
- **内置三组样例（PRD §9.1）**：`samples/sample_campus.json`、`sample_culture.json`、`sample_brand.json`；侧栏一键载入。
- **导出**：运行成功后，在「导出」Tab 下载 **Markdown** 或 **Word（.docx）**；「内容」Tab 内修改文案后，导出会使用**编辑后**文本。
- **语言**：设置页切换 **中文 / English**（工作台主要 Tab 与按钮）。
- **模型分流**：设置页开启「D 小模型 / C 大模型」，默认 `gpt-4o-mini`（D）与 `gpt-4o`（C），见 `config.yaml` 的 `llm.model_d` / `model_c`。

## 数据落盘

- SQLite：`data/operai.sqlite3`（任务、run、步骤、artifacts）。
- JSONL：`data/logs/<run_id>.jsonl`（每步事件，便于 zip 举证）。

## Harness 架构（W1）

W1 将硬编码 **D→C→N** 升级为可配置 **Pack + 插件注册表 + DAG** 骨架（默认仍跑 MEDIA Pack 的 `D→C→N` Mock/LLM）。

| 组件 | 路径 | 职责 |
|------|------|------|
| **Pack** | `packs/media/pack.yaml` | 默认 DAG、平台、校验策略 |
| **Pack Loader** | `src/harness/pack_loader.py` | `load_pack` / `list_packs` |
| **Plugin Registry** | `src/harness/plugin_registry.py` | 十 Agent 注册与 `invoke` |
| **DAG Runner** | `src/harness/dag_runner.py` | 按 DAG 顺序执行并注入 `upstream` |
| **Verify Gate** | `src/harness/verify_gate.py` | 一致性 + 敏感词，决定是否 `block_export` |
| **Orchestrator** | `src/orchestrator.py` | 统一入口；`harness.use_dag_runner` 或 `USE_HARNESS_DAG=1` 走 DAG |

- **十 Agent 契约（键名不可变）**：[docs/agent-plugin-contract.md](docs/agent-plugin-contract.md)
- **W1 工程清单**：[docs/W1-engineering-checklist.md](docs/W1-engineering-checklist.md)
- **插件状态**：D / C / N = `ready`；U / A / P / M / F / S / E = `stub`（Mock 可 invoke）
- **Harness 冒烟**（Mock，无需 Key）：

```powershell
$env:OPERAI_MOCK="1"
.\scripts\smoke_harness.ps1
```

- 关闭 DAG、回退 legacy：`$env:USE_HARNESS_DAG="0"` 或 `config.yaml` 中 `harness.use_dag_runner: false`

## 编排说明

见 `docs/orchestrator-state.md`（含 Mermaid 状态图）。

## 工作台页面

| 页面 | 说明 |
|------|------|
| 工作台 `app.py` | 六 Tab：输入 / 洞察 D / 内容 C / 分发 N / 运行轨迹 / 导出 |
| 任务列表 | 搜索、分页、复制/删除任务、按 run 打开、**两次 run C 文案 diff** |
| 设置 | Mock、模型、温度、短输出、跳过人审、**敏感词编辑**、**中英文界面**、**D/C 模型分流** |

## 已知限制

- LLM 返回非 JSON 时走 `llm_json` 修复与 Agent 降级（`_operai_fallback`），不中断整链。
- 未实现真实平台 OAuth 发帖（PRD Won’t）。
