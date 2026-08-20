# 小红书快消文案 QC 组件｜技术栈选型 v0.1

## 1. 当前还缺什么

### 已经明确

- P0 先搭轻量流程框架，内容质量优化放在 P1。
- 用户上传项目 Brief；每个文案类型也可单独上传类型 Brief。
- 拆解结果可视化并允许用户修改。
- 文案类型不预设，模板只留扩展接口。
- 帖子类型可空白建立、从类型 Brief 建立，或由用户提供一篇爆款参考文案后抽取结构与风格画像建立。
- 生成文案进入看板，不单独设置“一轮修改/二轮修改”列。
- 个例 QC 在生成后出现，以人工审核为主。
- 人工可直接编辑，或选中文字后输入方向让 AI 定向修改。
- 强制通过必须保留遗留问题。
- RapidFuzz 用于批次文本相似度初筛。
- 模型 API 和飞书开放平台能力由用户后续提供。

### 已固化的 P0 口径

1. **运行范围**：P0 默认本机 Windows、单用户、单个活跃项目；数据结构保留 `project_id`，方便以后多项目。
2. **输出结构**：每条文案为`类型、标题、正文、话题标签`，并附带稳定 `item_id`、完成方式、遗留问题和修改说明。
3. **图片范围**：P0 暂定只处理文案，不生成封面或配图；“图文”中的图片能力需要另行确认。
4. **Brief 文件范围**：P0 支持粘贴文本、`.txt`、`.md`、`.docx`；PDF、Excel、图片和 OCR 放到 P1。
5. **看板状态**：固定为`待 AI QC → AI QC 中 → AI 修改中 → 待人工审核 → 已完成`，修改轮次只显示为卡片计数。
6. **异常处理**：模型调用失败、超过重试上限和规则冲突都进入`待人工审核`，使用问题标签区分，不新增异常列。
7. **相似度阈值**：P0 提供可配置阈值和结果展示；默认值只用于试运行，P1 再用真实样本校准。
8. **飞书范围**：一个项目对应一份电子表格，每次输出新增子 Sheet；API 凭证和电子表格标识后续从 `.env` 提供。

## 2. 推荐技术栈

### 前端

| 选择 | 用途 | 选型理由 |
|------|------|----------|
| React | 看板、编辑器、弹窗和状态交互 | 交互复杂度已经超过纯原生 JS 的舒适范围，但不需要完整全栈框架 |
| TypeScript | 卡片、状态、QC 结果类型约束 | 避免前后端字段和状态名称漂移 |
| Vite | 开发与构建 | 配置少、构建快，可输出静态文件给 FastAPI 托管 |
| 原生 CSS / CSS Modules | 视觉样式 | 不引入 Ant Design、MUI、Tailwind 等大体系，保持界面独立和轻量 |
| 原生 Fetch + React Hooks | API 与页面状态 | P0 不引入 Redux、Zustand、TanStack Query |

#### 看板拖动

P0 不引入拖拽库，也不提供原生跨列拖动。卡片状态由工作流动作推进；如果后续确有人工排序需求，再单独设计可访问的排序交互。

原因：dnd-kit 功能完整且重视可访问性，但新 API 仍在快速演进；当前看板主要用于显示 AI 进度，状态通常由系统推进，不需要用户频繁拖动。

### 后端

| 选择 | 用途 | 选型理由 |
|------|------|----------|
| Python 3.12 | 服务运行时 | RapidFuzz、文档解析和后续模型 API 接入生态合适 |
| FastAPI | REST API、上传、静态文件 | 基于类型声明生成 OpenAPI，适合前后端契约和后续 API 适配 |
| Pydantic v2 | 输入输出数据模型 | 结构化文案、QC 结果和 Brief 拆解均需要严格 Schema |
| Uvicorn | 本地 ASGI 服务 | 单机运行足够轻量 |
| Python `sqlite3` | 持久化 | SQLite 单文件、事务可靠，无需额外数据库服务或 ORM |
| HTTPX | 外部 API | 后续连接模型和飞书 REST API；当前只保留适配器 |

### 文档与 QC

| 选择 | 用途 | P0 范围 |
|------|------|---------|
| RapidFuzz | 批次内及生成稿与爆款参考之间的标题、开头和正文近重复检查 | 直接依赖，先做字符级相似度 |
| python-docx | 提取 Word Brief | 只读取段落与表格文字 |
| Python `re` | 禁用词、必含词、格式规则 | 作为确定性 QC |
| `unicodedata` | 全半角和 Unicode 归一化 | RapidFuzz 比较前统一处理 |

### 测试

| 选择 | 用途 |
|------|------|
| pytest + FastAPI TestClient | API、规则、状态流转与 SQLite 测试 |
| Playwright | 看板、编辑、右键定向修改和强制通过的真实浏览器测试 |
| TypeScript 编译检查 | 前端类型错误与前后端字段漂移 |

## 3. 建议的部署形态

### 开发时

```text
Vite 开发服务（前端）
        ↓ REST
FastAPI（后端）
        ↓
SQLite + 本地上传文件
```

### 交付时

```text
浏览器
  ↓
FastAPI 单进程
  ├─ 托管 Vite 构建后的静态页面
  ├─ REST API
  ├─ SQLite 数据库
  ├─ ModelAdapter（等待用户 API）
  └─ FeishuExporter（等待开放平台能力）
```

用户只需要启动一个本地服务，不需要单独启动 Node、数据库、Redis 或任务队列。

## 4. P0 状态设计

```text
待 AI QC
    ↓
AI QC 中
    ├─ 通过 ──────────────→ 已完成（AI 自动通过）
    └─ 未通过 → AI 修改中 ─→ 待 AI QC
                         （attempt + 1）

达到重试上限 / API 失败 / 硬规则冲突
    └────────────────────→ 待人工审核

待人工审核
    ├─ 人工通过 ──────────→ 已完成
    ├─ 强制通过 + 遗留问题 → 已完成
    ├─ 人工定向 AI 修改 ──→ AI 修改中 → 待人工审核
    └─ 未通过（保留在人工审核，不输出）
```

看板只有五栏；`attempt`、API 错误、硬/软问题和审核状态显示在卡片上。

## 5. 数据与任务策略

- 使用 SQLite，不使用 JSON 作为权威数据源。
- 上传文件保存在本地项目数据目录，数据库只保存生成后的安全文件名和路径。
- 主要实体：`projects`、`briefs`、`copy_types`、`qc_rules`、`copy_items`、`qc_runs`、`rewrite_requests`、`review_events`、`export_runs`。
- 每次人工修改、AI 修改、通过和强制通过都写入事件记录，不覆盖历史。
- P0 使用数据库任务表和同进程异步执行，不引入 Celery、Redis、RabbitMQ 或 LangGraph。
- 页面每 2–3 秒轮询任务状态；P0 不使用 WebSocket。

## 6. 模型与飞书接口边界

### 模型

模型供应商固定为 CLIPROXY，但不引入 OpenAI SDK、Pydantic AI 或其他模型框架。使用 HTTPX 实现独立 `CliProxyModelAdapter`，内部仍定义项目自己的接口：

```text
parse_brief()
generate_copy()
run_semantic_qc()
rewrite_copy()
rewrite_selection()
```

CLIPROXY Base URL、API Key、生成/QC 模型名、reasoning effort 和 timeout 从 `.env` 读取。Adapter 采用 Responses 兼容请求并通过合同测试验证；供应商字段变化只修改 Adapter，不修改业务流程。

### 飞书

当前只定义：

```text
create_project_spreadsheet()
append_run_sheet()
write_run_rows()
```

实际鉴权、权限和字段写入在用户提供飞书开放平台能力后实现。

## 7. 明确不选

- Next.js：当前没有 SSR、SEO 或服务端 React 需求。
- Ant Design / MUI：会让轻量看板变成重型后台系统，并限制视觉方向。
- Redux / Zustand：P0 状态规模不足以支持额外状态库。
- SQLAlchemy / SQLModel：P0 表结构可控，直接使用 SQLite 更轻。
- PostgreSQL / MySQL：单机单用户不需要数据库服务。
- Celery / Redis：模型接入前不需要外部任务队列。
- LangGraph：当前流程是有限状态机，不需要通用 Agent 编排。
- Promptfoo / DeepEval / Guardrails 作为在线依赖：P1 可用 DeepEval 做回归评测，但不进入生产流程。
- Pydantic AI：在模型 API 协议明确前不提前绑定。

## 8. 推荐结论

```text
Frontend: React + TypeScript + Vite + 自定义 CSS
Backend:  Python 3.12 + FastAPI + Pydantic v2 + Uvicorn
Storage:  SQLite（Python sqlite3）+ 本地文件目录
QC:       Python 确定性规则 + RapidFuzz
API:      REST + 2–3 秒轮询
Testing:  pytest + Playwright + TypeScript check
Deploy:   FastAPI 托管前端静态产物，单进程本地运行
```

这是当前在“交互可维护”和“能轻量则轻量”之间最稳妥的组合。
