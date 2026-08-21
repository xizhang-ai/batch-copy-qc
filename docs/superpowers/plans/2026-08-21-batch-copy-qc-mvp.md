# 小红书快消种草批量文案与 QC MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个独立、单机、单用户的轻量 Web 产品，支持项目/类型 Brief 拆解、批量文案生成、确定性与模型 QC、异常人工审核、版本留痕，并为模型 API 与飞书子 Sheet 输出保留可替换适配层。

**Architecture:** 前端为 React + TypeScript + Vite 单页应用，后端为 FastAPI 单体服务，SQLite 是唯一权威存储。生成、QC 与改写由 SQLite 状态和同进程任务执行器驱动；模型使用独立 `CliProxyModelAdapter`，飞书通过 Protocol 适配器隔离。开发与验收使用确定性 Fake Adapter，填入 `.env` 后切换 CLIPROXY，不改业务状态机。

**Tech Stack:** React 19、TypeScript、Vite、React Router、原生 Fetch/CSS；Python 3.12、FastAPI、Pydantic v2、Uvicorn、sqlite3、HTTPX、python-docx、RapidFuzz；CLIPROXY Responses 兼容 API；pytest、Vitest、Testing Library、Playwright。

---

## 0. 执行边界

本计划是“长任务编码前的最后一步”。当前不执行复选框、不安装依赖、不创建应用源码。

### P0 必做

- 项目创建、列表和归档。
- 粘贴或上传 `.txt`、`.md`、`.docx` 项目 Brief。
- AI 拆解项目内容、文案需求、QC 需求和待确认内容，并提供原文依据与置信度。
- 用户可编辑拆解结果，明确保存后才进入后续步骤。
- 文案类型初始为空；用户新增空白类型，可输入或上传类型 Brief，填写生成数量。
- 帖子类型可组合使用“参考案例”和“描述要求”；一篇爆款案例即可建立类型，同一类型最多 5 篇。原帖完整保存，AI 抽取可编辑风格画像，生成 Prompt 同时携带原帖与画像，但不得继承来源事实或照搬原句。
- 用户未单独填写类型 QC 时，“一定要有/一定不要有”自动转为可见、可编辑的默认类型 QC。
- 项目级与类型级硬/软 QC 规则，可编辑、启停和处理冲突。
- 批量生成标题、正文、标签，并为每条成稿建立稳定 `item_id`。
- 看板固定五列：待 AI QC、AI QC 中、AI 修改中、待人工审核、已完成。
- AI QC 通过直接完成；自动修改后重新 AI QC；异常项进入人工审核。
- 人工可直接编辑，或选中文字输入方向让 AI 定向修改；定向修改后返回人工审核。
- 人工通过、强制通过；强制通过遗留问题必填。
- SQLite 保存配置、文案版本、QC、修改、审核和输出记录。
- 飞书适配协议、幂等输出运行与 `.env` 配置边界；真实传输在凭证与协议提供后接入。
- 完整测试、演示夹具和 Windows 本地启动文档。

### P0 不做

- 内置模板、模板市场或保存为模板。
- PDF、Excel、图片解析或 OCR。
- 图片生成、自动发布小红书。
- 多用户、权限、云端协作、多租户。
- 拖拽看板、复杂富文本编辑器、WebSocket。
- 模型训练和文案质量深度调优。
- Celery、Redis、RabbitMQ、LangGraph 或外部数据库。

## 1. 冻结状态机

```text
生成成功
  → pending_ai_qc
  → ai_qc_running
      ├─ 全部通过
      │    → completed / completion_reason=ai_pass
      ├─ 内容 finding 仍未通过，且 auto_rewrite_count < AUTO_REWRITE_LIMIT
      │    → ai_rewrite_running
      │    → pending_ai_qc
      └─ 低置信度 / 系统或模型异常 /
          v5 复检仍未通过
           → human_review

human_review
  ├─ 直接编辑 → human_review
  ├─ 人工选区 AI 修改 → ai_rewrite_running(origin=human) → human_review
  ├─ 人工通过 → completed / completion_reason=human_pass
  ├─ 强制通过 + 非空遗留问题
  │    → completed / completion_reason=forced_pass
  └─ 未通过 → human_review / review_disposition=rejected
```

`workflow_status` 与 `completion_reason` 必须分开：

```python
WorkflowStatus = Literal[
    "pending_ai_qc",
    "ai_qc_running",
    "ai_rewrite_running",
    "human_review",
    "completed",
]

CompletionReason = Literal["ai_pass", "human_pass", "forced_pass"]
ReviewDisposition = Literal["open", "rejected"]
```

## 2. 目标文件结构

```text
batch-copy-qc/
├─ .env.example
├─ .gitignore
├─ README.md
├─ pyproject.toml
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ config.py
│  │  ├─ lifespan.py
│  │  ├─ api/
│  │  │  ├─ errors.py
│  │  │  ├─ system.py
│  │  │  ├─ projects.py
│  │  │  ├─ copy_types.py
│  │  │  ├─ qc_rules.py
│  │  │  ├─ runs.py
│  │  │  ├─ items.py
│  │  │  └─ exports.py
│  │  ├─ domain/
│  │  │  ├─ enums.py
│  │  │  ├─ schemas.py
│  │  │  ├─ transitions.py
│  │  │  └─ errors.py
│  │  ├─ db/
│  │  │  ├─ connection.py
│  │  │  ├─ migrations.py
│  │  │  ├─ repositories.py
│  │  │  └─ migrations/001_initial.sql
│  │  ├─ brief/
│  │  │  ├─ extraction.py
│  │  │  ├─ storage.py
│  │  │  └─ service.py
│  │  ├─ model/
│  │  │  ├─ protocol.py
│  │  │  ├─ fake.py
│  │  │  ├─ cliproxy.py
│  │  │  └─ factory.py
│  │  ├─ generation/
│  │  │  ├─ service.py
│  │  │  └─ worker.py
│  │  ├─ qc/
│  │  │  ├─ deterministic.py
│  │  │  ├─ similarity.py
│  │  │  ├─ merge_rules.py
│  │  │  └─ service.py
│  │  ├─ review/service.py
│  │  └─ export/
│  │     ├─ protocol.py
│  │     ├─ fake.py
│  │     ├─ factory.py
│  │     └─ service.py
│  └─ tests/
│     ├─ conftest.py
│     ├─ fixtures/
│     ├─ unit/
│     ├─ integration/
│     └─ contract/
├─ frontend/
│  ├─ package.json
│  ├─ vite.config.ts
│  ├─ tsconfig.json
│  ├─ index.html
│  └─ src/
│     ├─ main.tsx
│     ├─ app/router.tsx
│     ├─ api/client.ts
│     ├─ api/contracts.ts
│     ├─ styles/tokens.css
│     ├─ styles/global.css
│     ├─ components/
│     └─ features/
│        ├─ shell/
│        ├─ projects/
│        ├─ project-content/
│        ├─ copy-types/
│        ├─ qc-rules/
│        ├─ board/
│        ├─ review/
│        └─ export/
├─ examples/
│  ├─ demo-project-brief.md
│  ├─ demo-type-brief.md
│  └─ demo-project-qc.md
├─ e2e/
│  ├─ playwright.config.ts
│  └─ specs/happy-path.spec.ts
└─ docs/
   ├─ brief-proposal.md
   ├─ tech-stack-selection.md
   ├─ frontend-visual-spec-v0.1.md
   ├─ external-integration-contract.md
   └─ superpowers/plans/2026-08-21-batch-copy-qc-mvp.md
```

## 3. 数据模型

`001_initial.sql` 创建以下表；JSON 字段以 TEXT 保存，但写入前后必须由 Pydantic 校验：

| 表 | 核心字段 | 责任 |
|---|---|---|
| `projects` | `id`, `name`, `category`, `brand`, `structured_json`, `status`, timestamps | 项目确认数据 |
| `brief_sources` | `id`, `project_id`, `copy_type_id`, `scope`, `filename`, `stored_path`, `extracted_text`, `classification_json`, `parse_status` | 原始 Brief、未分类文件与爆款参考来源 |
| `copy_types` | `id`, `project_id`, `name`, `quantity`, `input_modes_json`, `requirements_json`, `must_include_json`, `must_avoid_json`, `reference_profile_json`, `template_id`, `template_version`, `position` | 用户自定义帖子类型及组合依据 |
| `reference_examples` | `id`, `copy_type_id`, `position`, `raw_text`, `title`, `body`, `topics_json`, `source_brief_id` | 一至五篇配对且保留原文的爆款参考案例 |
| `qc_rules` | `id`, `project_id`, `copy_type_id`, `scope`, `level`, `category`, `statement`, `source_kind`, `source_evidence`, `enabled` | 项目/类型硬软规则与默认约束来源 |
| `generation_runs` | `id`, `project_id`, `status`, `configuration_snapshot_json`, `total_requested`, counters, timestamps | 一次生成批次及项目/类型/规则/参考快照 |
| `copy_items` | `id`, `run_id`, `copy_type_id`, `ordinal`, content, `workflow_status`, `completion_reason`, counters | 当前成稿与看板状态 |
| `copy_item_versions` | `id`, `item_id`, `version`, `origin`, content, `change_note`, `created_at` | 不可变内容历史 |
| `qc_runs` | `id`, `item_id`, `item_version`, `trigger`, `status`, `similarity_score`, `model_name`, timestamps | 一次 QC 执行 |
| `qc_findings` | `id`, `qc_run_id`, `rule_id`, `level`, `category`, `status`, `message`, `evidence`, `suggestion`, `auto_fixable`, `confidence` | 可定位问题 |
| `rewrite_requests` | `id`, `item_id`, `origin`, selected range/text, `instruction`, versions, `status`, error | 自动或人工定向改写 |
| `review_events` | `id`, `item_id`, `event_type`, `reason`, `legacy_issues_json`, `created_at` | 人工决定审计 |
| `export_runs` | `id`, `project_id`, `generation_run_id`, `status`, `sheet_id`, `sheet_title`, `row_count`, error | 幂等飞书输出 |
| `model_call_logs` | `id`, operation, adapter/model, status, duration, token counts, safe error | 成本与错误诊断 |

关键数据库约束：

- 所有 ID 使用 UUID 字符串；`copy_items.id` 在所有版本与重写中保持稳定。
- `copy_item_versions(item_id, version)` 唯一。
- `copy_items(run_id, copy_type_id, ordinal)` 唯一。
- `copy_types.input_modes_json` 只能组合 `reference_examples` 与 `description_requirements`；至少一种有实际内容。启用参考案例时必须关联 1–5 条完整 reference example 和非空 reference profile。
- 没有任何 `source_kind=explicit_type_qc` 规则时，`must_include` 与 `must_avoid` 自动物化为 `source_kind=derived_type_constraint` 的可编辑默认 QC。
- `qc_rules.copy_type_id` 在项目级规则上必须为空，在类型级规则上必须非空。
- `completed` 必须有 `completion_reason`；非 `completed` 必须没有 `completion_reason`。
- `forced_pass` 必须存在非空遗留问题 review event。
- `export_runs.id` 是幂等键；已有 `sheet_id` 的失败重试不得新建子 Sheet。

## 4. REST 契约概览

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/health` | 服务状态 |
| GET | `/api/system/connections` | 返回模型/飞书是否配置，不返回秘密 |
| POST/GET | `/api/projects` | 建立/列出项目 |
| GET/PATCH | `/api/projects/{project_id}` | 项目详情/保存确认数据 |
| POST | `/api/projects/{project_id}/briefs:parse` | 粘贴或上传项目 Brief 并拆解 |
| POST/GET | `/api/projects/{project_id}/copy-types` | 新建空白类型/列出类型 |
| PATCH/DELETE | `/api/copy-types/{copy_type_id}` | 保存/删除类型 |
| POST | `/api/copy-types/{copy_type_id}/briefs:parse` | 解析类型 Brief |
| POST | `/api/copy-types/{copy_type_id}/references:analyze` | 解析 1–5 篇完整爆款案例并生成可编辑风格画像 |
| POST | `/api/projects/{project_id}/type-files:classify` | 上传多个未分类类型文件并返回分类建议 |
| PATCH | `/api/brief-sources/{brief_source_id}` | 用户确认或修改文件归属 |
| GET/POST | `/api/projects/{project_id}/qc-rules` | 查询/新增规则 |
| PATCH/DELETE | `/api/qc-rules/{rule_id}` | 编辑/删除规则 |
| POST | `/api/projects/{project_id}/generation-runs` | 创建生成批次 |
| GET | `/api/generation-runs/{run_id}` | 轮询批次状态 |
| GET | `/api/projects/{project_id}/board` | 五列看板与一致统计 |
| GET/PATCH | `/api/items/{item_id}` | 详情/人工直接编辑 |
| POST | `/api/items/{item_id}/qc:retry` | 单条重试 QC |
| POST | `/api/items/{item_id}/rewrite-selection` | 人工选区定向修改 |
| POST | `/api/items/{item_id}/review` | reject/pass/force_pass/recall |
| POST | `/api/projects/{project_id}/exports` | 创建幂等输出运行，仅选 completed |
| GET/POST | `/api/export-runs/{export_id}`、`/api/export-runs/{export_id}:retry` | 轮询/重试输出 |

错误统一为：

```json
{
  "error": {
    "code": "ITEM_TRANSITION_INVALID",
    "message": "当前状态不能执行该操作",
    "details": {}
  }
}
```

## Task 1: 初始化独立项目骨架

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `pyproject.toml`
- Create: `backend/__init__.py`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/test_health.py`
- Create: `backend/tests/conftest.py`
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`

- [ ] **Step 1: 初始化独立 Git 仓库**

Run: `git init`

Expected: 仓库根目录是 `E:\xixiAi\batch-copy-qc`，父目录和其他产品不进入版本控制。

- [ ] **Step 2: 写后端健康检查失败测试**

```python
def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 3: 建立测试 client fixture**

`backend/tests/conftest.py`：

```python
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
```

- [ ] **Step 4: 建立 Python 依赖声明**

`pyproject.toml` 固定 Python `>=3.12,<3.13`，运行依赖包含 FastAPI、Uvicorn、Pydantic Settings、HTTPX、python-docx、RapidFuzz、python-multipart；开发依赖包含 pytest、pytest-asyncio、ruff。

- [ ] **Step 5: 运行失败测试**

Run: `python -m pytest backend/tests/test_health.py -q`

Expected: FAIL，原因是 `backend.app.main` 或 `/api/health` 尚不存在。

- [ ] **Step 6: 实现最小 FastAPI 应用**

```python
from fastapi import FastAPI

app = FastAPI(title="种草文案 QC", version="0.1.0")

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 7: 初始化 Vite React 应用并显示“种草文案 QC”**

前端只添加 React、React DOM、React Router；开发依赖添加 Vite、TypeScript、Vitest、Testing Library、Playwright 所需包，不引入 UI 框架、状态库或拖拽库。脚本固定为 `dev`、`build`、`typecheck`、`test` 和 `test:e2e`，并生成 lockfile。

- [ ] **Step 8: 验证骨架**

Run: `python -m pytest backend/tests/test_health.py -q`

Expected: `1 passed`。

Run: `npm --prefix frontend run typecheck && npm --prefix frontend run build`

Expected: 两条命令退出码均为 0。

- [ ] **Step 9: 提交**

```bash
git add .gitignore .env.example pyproject.toml backend frontend
git commit -m "chore: scaffold standalone copy qc app"
```

## Task 2: 配置、领域枚举与合法状态转换

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/domain/enums.py`
- Create: `backend/app/domain/transitions.py`
- Create: `backend/app/domain/errors.py`
- Test: `backend/tests/unit/test_transitions.py`

- [ ] **Step 1: 写状态转换测试**

```python
def test_ai_pass_completes_without_human_review():
    result = apply_transition("ai_qc_running", "ai_pass")
    assert result.status == "completed"
    assert result.completion_reason == "ai_pass"

def test_human_guided_rewrite_returns_to_human_review():
    result = apply_transition("ai_rewrite_running", "human_rewrite_succeeded")
    assert result.status == "human_review"

def test_forced_pass_requires_legacy_issues():
    with pytest.raises(DomainError, match="遗留问题"):
        apply_transition("human_review", "force_pass", legacy_issues=[])
```

- [ ] **Step 2: 定义字符串枚举**

定义 `WorkflowStatus`、`CompletionReason`、`RuleLevel`、`RewriteOrigin`、`ReviewDisposition`，所有数据库和 API 只使用这些枚举值。

- [ ] **Step 3: 实现纯函数状态转换**

`apply_transition(current, event, legacy_issues=None)` 返回不可变 `TransitionResult`；非法事件抛出带 `code="ITEM_TRANSITION_INVALID"` 的 `DomainError`。

- [ ] **Step 4: 定义 `.env` 配置字段**

```dotenv
APP_ENV=development
DATABASE_PATH=./data/batch-copy-qc.sqlite3
UPLOAD_DIR=./data/uploads
MODEL_ADAPTER=fake
CLIPROXY_BASE_URL=
CLIPROXY_API_KEY=
CLIPROXY_GENERATION_MODEL=
CLIPROXY_QC_MODEL=
CLIPROXY_REASONING_EFFORT=medium
CLIPROXY_TIMEOUT_SECONDS=120
MODEL_CONCURRENCY=2
AUTO_REWRITE_LIMIT=4
API_RETRY_LIMIT=2
SIMILARITY_THRESHOLD=85
QC_CONFIDENCE_THRESHOLD=0.70
FEISHU_ADAPTER=unconfigured
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_SPREADSHEET_TOKEN=
```

前端不得接收 `CLIPROXY_API_KEY`、`FEISHU_APP_SECRET` 等秘密字段。

- [ ] **Step 5: 运行测试和静态检查**

Run: `python -m pytest backend/tests/unit/test_transitions.py -q && python -m ruff check backend`

Expected: 全部通过。

- [ ] **Step 6: 提交**

```bash
git add .env.example backend/app/config.py backend/app/domain backend/tests/unit/test_transitions.py
git commit -m "feat: define copy qc workflow states"
```

## Task 3: SQLite 迁移与事务仓储

**Files:**
- Create: `backend/app/db/connection.py`
- Create: `backend/app/db/migrations.py`
- Create: `backend/app/db/migrations/001_initial.sql`
- Create: `backend/app/db/repositories.py`
- Test: `backend/tests/integration/test_database.py`

- [ ] **Step 1: 写迁移幂等测试**

```python
def test_migrations_are_idempotent(temp_database):
    migrate(temp_database)
    migrate(temp_database)
    tables = table_names(temp_database)
    assert {"projects", "copy_items", "qc_runs", "export_runs"} <= tables
```

- [ ] **Step 2: 编写 `001_initial.sql`**

按“数据模型”章节建立 12 张表、外键、唯一索引、状态 CHECK 和 `schema_migrations`；启用 `PRAGMA foreign_keys=ON`、`journal_mode=WAL`、`busy_timeout=5000`。

- [ ] **Step 3: 实现显式事务连接器**

```python
@contextmanager
def transaction(connection: sqlite3.Connection):
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
```

- [ ] **Step 4: 实现仓储最小接口**

仓储必须包含项目 CRUD、类型 CRUD、规则 CRUD、创建运行与 item、原子更新状态、追加版本、追加 QC finding、追加审核事件、创建/重试 export run。任何状态更新同时校验预期旧状态，避免重复轮询造成覆盖。

- [ ] **Step 5: 验证约束**

增加测试：重复 item 槽位失败、完成项缺少 completion reason 失败、强制通过服务拒绝空遗留问题、删除有生成记录的类型失败。

- [ ] **Step 6: 运行测试**

Run: `python -m pytest backend/tests/integration/test_database.py -q`

Expected: 全部通过且临时数据库文件可删除。

- [ ] **Step 7: 提交**

```bash
git add backend/app/db backend/tests/integration/test_database.py
git commit -m "feat: add sqlite persistence and migrations"
```

## Task 4: Brief 文件存储与文本提取

**Files:**
- Create: `backend/app/brief/storage.py`
- Create: `backend/app/brief/extraction.py`
- Test: `backend/tests/unit/test_brief_extraction.py`
- Create: `backend/tests/fixtures/sample.docx`

- [ ] **Step 1: 写支持格式测试**

```python
@pytest.mark.parametrize("name", ["brief.txt", "brief.md", "brief.docx"])
def test_supported_brief_files_are_extracted(name, fixture_file):
    text = extract_text(name, fixture_file)
    assert "清爽气泡水" in text

def test_pdf_is_rejected_in_p0():
    with pytest.raises(UnsupportedBriefType):
        extract_text("brief.pdf", b"%PDF")
```

- [ ] **Step 2: 实现安全文件名与 UUID 存储**

保留原始显示名称，磁盘文件名使用 UUID；拒绝路径分隔符、空文件、单文件超过 10MB、项目附件总数超过 20。先写临时文件，成功后原子移动。

- [ ] **Step 3: 实现文本提取**

- `.txt`/`.md`：按 UTF-8 读取，带 BOM 时兼容 `utf-8-sig`。
- `.docx`：提取段落和表格单元格，保持阅读顺序。
- 归一化 CRLF、连续空行和 NUL 字符；空文本返回 `BRIEF_TEXT_EMPTY`。

- [ ] **Step 4: 验证失败不丢文件记录**

提取失败时 `brief_sources.parse_status=failed` 并保存安全错误码，禁止把异常堆栈返回前端。

- [ ] **Step 5: 运行测试并提交**

Run: `python -m pytest backend/tests/unit/test_brief_extraction.py -q`

Expected: 全部通过。

```bash
git add backend/app/brief backend/tests
git commit -m "feat: ingest text markdown and docx briefs"
```

## Task 5: 模型协议、CLIPROXY 与确定性 Fake Adapter

**Files:**
- Create: `backend/app/model/protocol.py`
- Create: `backend/app/model/fake.py`
- Create: `backend/app/model/cliproxy.py`
- Create: `backend/app/model/factory.py`
- Create: `backend/app/domain/schemas.py`
- Test: `backend/tests/contract/test_model_adapter.py`
- Test: `backend/tests/contract/test_cliproxy_adapter.py`

- [ ] **Step 1: 写模型协议契约测试**

```python
async def test_fake_adapter_returns_valid_structures(fake_model):
    parsed = await fake_model.parse_brief("项目名称：夏日气泡水", scope="project")
    assert parsed.sections.project_content
    profile = await fake_model.analyze_reference_examples(make_reference_examples())
    assert profile.hook_pattern and profile.structure
    draft = await fake_model.generate_copy(make_generation_context())
    assert draft.title and draft.body and draft.tags
```

- [ ] **Step 2: 定义六个模型操作**

```python
class ModelAdapter(Protocol):
    async def parse_brief(self, text: str, scope: BriefScope) -> BriefParseResult:
        raise NotImplementedError
    async def analyze_reference_examples(self, context: ReferenceExamplesContext) -> ReferenceStyleProfile:
        raise NotImplementedError
    async def generate_copy(self, context: GenerationContext) -> CopyDraft:
        raise NotImplementedError
    async def run_semantic_qc(self, context: SemanticQcContext) -> SemanticQcResult:
        raise NotImplementedError
    async def rewrite_copy(self, context: RewriteContext) -> CopyDraft:
        raise NotImplementedError
    async def rewrite_selection(self, context: SelectionRewriteContext) -> str:
        raise NotImplementedError
```

所有返回值为禁止额外字段的 Pydantic 模型；Brief finding 包含 `value`、`source_quote`、`confidence`、`section`，不得自动填充原文缺失事实。`ReferenceExamplesContext` 包含 1–5 个配对的 raw_text/title/body/topics。`ReferenceStyleProfile` 固定包含标题钩子、开头方式、结构节拍、叙事视角、语气、人设、场景、信息密度、卖点顺序、结尾策略、标签策略、来源事实和避免照搬表达。

- [ ] **Step 3: 实现可重复 Fake Adapter**

Fake 结果只由输入哈希决定；支持测试标记 `[FAIL_QC]`、`[MODEL_ERROR]`、`[LOW_CONFIDENCE]`，不得调用网络。参考分析必须把虚构品牌、价格和功效放入 `source_facts_to_exclude`，而不是当前项目 requirements。

- [ ] **Step 4: 写 CLIPROXY HTTP 合同测试**

使用 `httpx.MockTransport` 断言请求路径为 `/v1/responses`、鉴权为 `Bearer`、请求含 model/instructions/input/max_output_tokens 和可选 reasoning；分别覆盖顶层 `output_text` 与 `output[].content[].text`。增加 401、429、超时、非 JSON、空输出和业务 JSON 不符合 Pydantic schema 的错误映射测试。

- [ ] **Step 5: 实现 `CliProxyModelAdapter`**

使用 `httpx.AsyncClient` 和 `.env` 配置；`run_semantic_qc` 使用 `CLIPROXY_QC_MODEL`，其余五个操作使用 `CLIPROXY_GENERATION_MODEL`。每个操作有独立 system instructions 和严格输出 schema；生成 Prompt 必须包含项目事实、1–5 篇原参考帖、确认画像、描述要求、must/avoid 与有效 QC 规则，并明确来源事实和独特原句禁用。

HTTP 错误映射为 `MODEL_AUTH_FAILED`、`MODEL_RATE_LIMITED`、`MODEL_TIMEOUT`、`MODEL_RESPONSE_INVALID`、`MODEL_UNAVAILABLE`，供应商原始 body 不返回前端。

- [ ] **Step 6: 实现工厂**

`MODEL_ADAPTER=fake` 返回 Fake；`MODEL_ADAPTER=cliproxy` 在所有必填 CLIPROXY 配置存在时返回真实 Adapter，缺失时启动失败并列出缺失变量名但不打印值；其他值返回 `MODEL_ADAPTER_UNSUPPORTED`。

- [ ] **Step 7: 记录安全模型调用日志**

记录 operation、adapter、model、duration、status、token counts 和错误码；不记录 API key，不默认保存完整 prompt。

- [ ] **Step 8: 运行测试并提交**

Run: `python -m pytest backend/tests/contract/test_model_adapter.py backend/tests/contract/test_cliproxy_adapter.py -q`

Expected: 全部通过。

```bash
git add backend/app/model backend/app/domain/schemas.py backend/tests/contract
git commit -m "feat: add cliproxy model adapter"
```

## Task 6: 项目建立与项目 Brief 可视化数据 API

**Files:**
- Create: `backend/app/api/errors.py`
- Create: `backend/app/api/projects.py`
- Create: `backend/app/brief/service.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_projects_api.py`

- [ ] **Step 1: 写创建与解析 API 测试**

测试创建项目返回 UUID；粘贴 Brief 后返回四区：项目内容、文案需求、QC 需求、待确认；每条内容包含依据和置信度。

- [ ] **Step 2: 实现项目 CRUD**

项目创建只要求名称；`PATCH` 使用完整 Pydantic schema 保存确认结果。服务器忽略客户端提交的 `created_at`、`project_id` 等只读字段。

- [ ] **Step 3: 实现 multipart Brief 解析端点**

请求必须二选一：`text` 或 `file`；成功后保存原文、模型拆解结果与来源；解析不直接覆盖已确认字段，而返回 `suggested_changes` 和 `conflicts`。

- [ ] **Step 4: 统一 API 错误**

把领域异常映射成固定 `{error:{code,message,details}}`；上传过大返回 413，格式不支持返回 415，模型未配置返回 503。

- [ ] **Step 5: 运行测试并提交**

Run: `python -m pytest backend/tests/integration/test_projects_api.py -q`

Expected: 全部通过。

```bash
git add backend/app/api backend/app/brief/service.py backend/app/main.py backend/tests/integration/test_projects_api.py
git commit -m "feat: add project brief workflow api"
```

## Task 7: 帖子类型组合依据、爆款案例画像与规则继承

**Files:**
- Create: `backend/app/api/copy_types.py`
- Create: `backend/app/api/qc_rules.py`
- Create: `backend/app/qc/merge_rules.py`
- Test: `backend/tests/unit/test_rule_merge.py`
- Test: `backend/tests/integration/test_copy_types_api.py`

- [ ] **Step 1: 写“无预设类型”测试**

新项目的类型列表必须为空；创建类型时名称和数量由用户提供，系统不得返回模板或默认类型。

- [ ] **Step 2: 写组合依据与爆款案例测试**

覆盖只用描述要求、只用一篇参考案例、案例与描述同时使用、5 篇案例成功、第 6 篇被拒绝、缺少标题或正文、原帖完整保存、来源事实隔离、画像确认后才能生成。

- [ ] **Step 3: 写规则优先级测试**

```python
def test_type_soft_rule_overrides_project_soft_rule():
    merged = merge_rules(project_rules=[soft("tone", "克制")], type_rules=[soft("tone", "活泼")])
    assert merged.effective[0].statement == "活泼"

def test_type_rule_cannot_override_project_hard_rule():
    merged = merge_rules(project_rules=[hard("claim", "不得宣称治疗")], type_rules=[soft("claim", "突出治疗效果")])
    assert merged.effective[0].statement == "不得宣称治疗"

def test_hard_conflict_is_returned_for_confirmation():
    merged = merge_rules(project_rules=[hard("claim", "不得宣称治疗")], type_rules=[soft("claim", "突出治疗效果")])
    assert merged.conflicts[0].category == "claim"
```

- [ ] **Step 4: 实现类型 CRUD 与类型 Brief 解析**

类型数量范围 1–100；项目所有类型合计不超过 100。类型 Brief 中的项目事实只返回“建议更新项目内容”或“事实冲突”，用户确认前不写入项目结构化数据。

- [ ] **Step 5: 实现参考案例与描述要求**

类型允许组合启用 `reference_examples` 与 `description_requirements`。参考案例按 raw_text/title/body/topics 完整保存并配对，数量 1–5；调用 `analyze_reference_examples` 形成可编辑画像。`must_include` 与 `must_avoid` 作为显式类型约束保存，优先于推断画像但不能覆盖项目硬规则。

没有单独输入类型 QC 时，服务把 must/avoid 生成 `derived_type_constraint` 默认 QC；用户后来新增显式类型 QC 时，默认规则继续可见并允许编辑或停用，不静默删除。生成上下文必须同时包含原参考帖全文、确认画像、描述要求和显式约束，并使用清晰分区标记“参考而非事实来源”和“禁止照搬”。

- [ ] **Step 6: 实现多文件分类建议与人工归属**

多个 txt/md/docx 文件先进入未分类区；模型只给建议类型、依据和置信度。用户可以改归已有类型、建立空白类型或保持未分类，系统不自动确认。

- [ ] **Step 7: 实现 QC 规则 CRUD**

规则字段固定为 scope、level、category、statement、source_evidence、enabled。项目硬规则永不被类型规则覆盖；类型软规则按 category 覆盖项目软规则。

- [ ] **Step 8: 运行测试并提交**

Run: `python -m pytest backend/tests/unit/test_rule_merge.py backend/tests/integration/test_copy_types_api.py -q`

Expected: 全部通过。

```bash
git add backend/app/api/copy_types.py backend/app/api/qc_rules.py backend/app/qc/merge_rules.py backend/tests
git commit -m "feat: add copy types and scoped qc rules"
```

## Task 8: 批次生成、稳定 item_id 与恢复式本地 Worker

**Files:**
- Create: `backend/app/generation/service.py`
- Create: `backend/app/generation/worker.py`
- Create: `backend/app/api/runs.py`
- Create: `backend/app/lifespan.py`
- Test: `backend/tests/integration/test_generation_run.py`

- [ ] **Step 1: 写生成批次测试**

确认项目和至少一个有效类型后才能生成；批次按各类型数量建立槽位。成功生成的每条 item 有稳定 ID、版本 1 和 `pending_ai_qc`。

- [ ] **Step 2: 实现运行前校验**

阻止未保存项目、空类型、数量越界、缺少产品事实、存在未确认硬冲突，以及启用了参考案例但风格画像尚未确认的项目启动。返回所有校验问题，不只返回第一项。

生成上下文按优先级合并：项目事实与硬规则 → 类型“一定要有/不要有” → 用户描述要求 → 已确认参考风格画像 → 1–5 篇原参考帖。Prompt 使用明确分区：`PROJECT_FACTS` 是唯一事实来源；`REFERENCE_EXAMPLES` 只学习写法；`SOURCE_FACTS_TO_EXCLUDE` 和 `PHRASES_NOT_TO_COPY` 禁止继承。运行创建时把本次项目、类型、规则、画像和原帖写入 `configuration_snapshot_json`，后续编辑不改变已启动批次。

- [ ] **Step 3: 实现受控并发 Worker**

使用 `asyncio.Queue` 与 `MODEL_CONCURRENCY`；每个槽位单独提交、单独失败。进程启动时把中断的 running 工作恢复为 queued；已经成功的 item 不重复生成。

- [ ] **Step 4: 实现轮询 API**

批次响应包含 requested、generated、failed、pending 和错误摘要；失败槽位可以单独重试，不能重建已成功 item。

- [ ] **Step 5: 验证重启与稳定 ID**

测试中断恢复后原 item ID 不变、版本历史不丢、成功项不重复调用模型。

- [ ] **Step 6: 运行测试并提交**

Run: `python -m pytest backend/tests/integration/test_generation_run.py -q`

Expected: 全部通过。

```bash
git add backend/app/generation backend/app/api/runs.py backend/app/lifespan.py backend/tests
git commit -m "feat: add recoverable batch generation"
```

## Task 9: 确定性 QC、批次相似度与参考案例防照搬

**Files:**
- Create: `backend/app/qc/deterministic.py`
- Create: `backend/app/qc/similarity.py`
- Test: `backend/tests/unit/test_deterministic_qc.py`
- Test: `backend/tests/unit/test_similarity.py`

- [ ] **Step 1: 写文本归一化与相似度测试**

```python
def test_normalization_handles_full_width_and_whitespace():
    assert normalize_for_similarity("Ａ  气泡水\n") == "a 气泡水"

def test_near_duplicate_chinese_copy_is_flagged():
    result = compare_items(item("a", "通勤喝气泡水"), [item("b", "通勤路上喝气泡水")], threshold=80)
    assert result[0].matched_id == "b"

def test_item_is_never_compared_with_itself():
    assert compare_items(item("a", "同一篇"), [item("a", "同一篇")], threshold=80) == []

def test_generated_copy_too_close_to_reference_is_flagged():
    result = compare_with_references(item("a", "午后第一口气泡水"), [reference("r1", "午后第一口气泡水")], threshold=80)
    assert result[0].source_kind == "reference_example"
```

- [ ] **Step 2: 实现归一化**

使用 Unicode NFKC、统一空白、去除比较无意义的标点差异；保存原文不变。标题、开头 80 字和全文分别计算 RapidFuzz ratio，返回最大风险分数、比较来源（批次 item 或 reference example）和匹配 ID。

- [ ] **Step 3: 实现最小确定性规则**

检查标题/正文字数、标题正文标签非空、类型“一定要有/不要有”、必含词、禁用词、标签格式、产品事实硬规则。每个 finding 返回 rule_id、level、category、message、evidence、suggestion、auto_fixable。

- [ ] **Step 4: 实现批次最少改写定位**

相似度配对只标记较后生成的 item 为候选改写项；较早 item 保留，除非人工另行选择。结果需要展示与哪个 item 相似。

与参考案例过近时只标记生成 item；任何来源品牌、价格、功效或独特原句命中都作为高风险 finding，自动改写必须保持当前项目事实不变。

- [ ] **Step 5: 运行测试并提交**

Run: `python -m pytest backend/tests/unit/test_deterministic_qc.py backend/tests/unit/test_similarity.py -q`

Expected: 全部通过。

```bash
git add backend/app/qc backend/tests/unit
git commit -m "feat: add deterministic and similarity qc"
```

## Task 10: AI QC 编排与自动修复循环

**Files:**
- Create: `backend/app/qc/service.py`
- Modify: `backend/app/generation/worker.py`
- Test: `backend/tests/integration/test_qc_workflow.py`

- [ ] **Step 1: 写直通和异常分支测试**

```python
async def test_ai_qc_pass_moves_item_directly_to_completed(qc_service, passing_item):
    result = await qc_service.run(passing_item.id)
    assert result.workflow_status == "completed"
    assert result.completion_reason == "ai_pass"

async def test_auto_fixable_failure_rewrites_then_rechecks(qc_service, auto_fixable_item):
    result = await qc_service.run(auto_fixable_item.id)
    assert result.workflow_status == "pending_ai_qc"
    assert result.auto_rewrite_count == 1

async def test_hard_conflict_moves_to_human_review(qc_service, hard_conflict_item):
    result = await qc_service.run(hard_conflict_item.id)
    assert result.workflow_status == "human_review"

async def test_retry_limit_moves_to_human_review(qc_service, exhausted_item):
    result = await qc_service.run(exhausted_item.id)
    assert result.workflow_status == "human_review"
```

- [ ] **Step 2: 实现 QC 顺序**

每次 QC 先运行确定性规则和批次相似度，再调用语义 QC。除模型低置信度或系统/模型异常外，所有内容类 finding 均先进入受 hard 规则约束的自动改写；hard 规则不可忽略或覆盖。初稿 v1 最多改写四次，v5 复检仍失败才进入人工审核。

- [ ] **Step 3: 实现 AI 通过直达完成**

单一事务中写入 QC run/findings、状态 `completed`、completion reason `ai_pass` 和系统审核事件。重复回调必须幂等。

- [ ] **Step 4: 实现自动改写限制**

自动改写写入新版本、`auto_rewrite_count + 1`，然后回 `pending_ai_qc`。`AUTO_REWRITE_LIMIT=4`，依次生成至 v5；v5 复检仍失败后停止调用模型并进入人工审核。

- [ ] **Step 5: 处理 API 异常**

网络类错误技术重试最多 2 次，退避不超过 10 秒；仍失败则保留当前文案，进入人工审核并显示安全错误码，不删除卡片。

- [ ] **Step 6: 运行测试并提交**

Run: `python -m pytest backend/tests/integration/test_qc_workflow.py -q`

Expected: 全部通过。

```bash
git add backend/app/qc/service.py backend/app/generation/worker.py backend/tests/integration/test_qc_workflow.py
git commit -m "feat: orchestrate ai qc and auto rewrite"
```

## Task 11: 人工编辑、选区 AI 修改与审核决定

**Files:**
- Create: `backend/app/review/service.py`
- Create: `backend/app/api/items.py`
- Test: `backend/tests/integration/test_review_api.py`

- [ ] **Step 1: 写人工审核不变量测试**

测试直接编辑后仍为 `human_review`；人工选区改写完成后仍为 `human_review`；普通通过在未解决硬规则存在时失败；强制通过空遗留问题失败。

- [ ] **Step 2: 实现乐观并发编辑**

`PATCH /items/{id}` 必须提交 `expected_version`；版本不一致返回 409，前端保留本地输入并提示重新加载。保存创建 `human_edit` 版本并重新执行确定性硬规则。

- [ ] **Step 3: 实现选区改写**

请求字段：`expected_version`、`field`、`selection_start`、`selection_end`、`selected_text`、`instruction`。后端验证切片仍与 selected_text 一致，防止旧选区覆盖新文本。

- [ ] **Step 4: 实现四种人工操作**

- `reject`：记录原因，保持 human_review，disposition=rejected。
- `pass`：必须无未解决硬规则，进入 completed/human_pass。
- `force_pass`：自动带入 unresolved findings，遗留问题非空，进入 completed/forced_pass。
- `recall`：把 completed 项召回 human_review，清空 completion reason，保留原完成事件。

- [ ] **Step 5: 运行测试并提交**

Run: `python -m pytest backend/tests/integration/test_review_api.py -q`

Expected: 全部通过。

```bash
git add backend/app/review backend/app/api/items.py backend/tests/integration/test_review_api.py
git commit -m "feat: add human review and guided rewrite"
```

## Task 12: 看板查询、统计一致性与单条重试

**Files:**
- Modify: `backend/app/api/items.py`
- Create: `backend/tests/integration/test_board_api.py`

- [ ] **Step 1: 写五列与统计测试**

响应必须始终包含五个固定 key；`total == sum(column.count)`；`ai_processing == ai_qc_running + ai_rewrite_running`。

- [ ] **Step 2: 实现看板查询**

支持 run、类型和完成方式筛选；卡片返回 item ID、自定义类型、标题预览、状态、问题计数、相似 item、修改次数、更新时间，不返回完整正文。

- [ ] **Step 3: 实现单条重试**

仅允许处于 human_review 且原因包含可重试系统错误的 item 回到 pending_ai_qc；普通人工拒绝不能伪装成系统重试。

- [ ] **Step 4: 运行测试并提交**

Run: `python -m pytest backend/tests/integration/test_board_api.py -q`

Expected: 全部通过。

```bash
git add backend/app/api/items.py backend/tests/integration/test_board_api.py
git commit -m "feat: expose consistent qc board data"
```

## Task 13: 飞书输出协议、幂等记录与 Fake Exporter

**Files:**
- Create: `backend/app/export/protocol.py`
- Create: `backend/app/export/fake.py`
- Create: `backend/app/export/factory.py`
- Create: `backend/app/export/service.py`
- Create: `backend/app/api/exports.py`
- Test: `backend/tests/contract/test_exporter.py`
- Test: `backend/tests/integration/test_export_runs.py`

- [ ] **Step 1: 写 exporter 协议测试**

```python
class FeishuExporter(Protocol):
    async def create_run_sheet(self, request: CreateRunSheet) -> SheetRef:
        raise NotImplementedError
    async def write_rows(self, sheet: SheetRef, rows: list[ExportRow]) -> None:
        raise NotImplementedError
```

- [ ] **Step 2: 固定输出列**

按顺序输出：序号、item_id、文案类型、标题、正文、话题标签、完成方式、遗留问题、修改说明。只有 completed 项可进入行集合。

- [ ] **Step 3: 实现 Fake Exporter**

Fake 返回稳定 `fake-{export_run_id}` sheet ID；测试通过依赖注入的内存记录器断言写入行，开发模式只在 `export_runs` 保存 sheet ID、状态和 row_count，不创建 JSON 权威文件，不调用网络。

- [ ] **Step 4: 实现幂等 ExportService**

第一次调用创建 export run；已有 sheet_id 的失败重试跳过 create，只重试固定行写入；成功 export run 再次提交返回原结果，不创建第二个 sheet。

- [ ] **Step 5: 实现连接状态 API**

`/api/system/connections` 仅返回 `{model:{configured,adapter}, feishu:{configured,adapter,spreadsheetConfigured}}`，不得返回 ID、secret 或 token 原值。

- [ ] **Step 6: 运行测试并提交**

Run: `python -m pytest backend/tests/contract/test_exporter.py backend/tests/integration/test_export_runs.py -q`

Expected: 全部通过。

```bash
git add backend/app/export backend/app/api/exports.py backend/tests
git commit -m "feat: add idempotent export boundary"
```

## Task 14: 前端 API 契约、错误处理与应用骨架

**Files:**
- Create: `frontend/src/api/contracts.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/app/router.tsx`
- Create: `frontend/src/features/shell/AppShell.tsx`
- Create: `frontend/src/styles/tokens.css`
- Create: `frontend/src/styles/global.css`
- Test: `frontend/src/api/client.test.ts`
- Test: `frontend/src/features/shell/AppShell.test.tsx`

- [ ] **Step 1: 写 same-origin API client 测试**

绝对 URL 必须被拒绝；非 2xx 响应解析统一 error code；无效 JSON 映射为 `API_RESPONSE_INVALID`。

- [ ] **Step 2: 定义与后端一致的 TypeScript union**

```ts
export type WorkflowStatus =
  | "pending_ai_qc"
  | "ai_qc_running"
  | "ai_rewrite_running"
  | "human_review"
  | "completed";

export type CompletionReason = "ai_pass" | "human_pass" | "forced_pass";
```

- [ ] **Step 3: 实现视觉 token**

逐项复制 `docs/frontend-visual-spec-v0.1.md` 的 OKLCH、间距、圆角、阴影、字号和状态映射；JSX 禁止出现散落色值。

- [ ] **Step 4: 实现应用壳**

桌面 16px 外边距、28px 主壳、72px 图标栏、48px 悬浮顶部导航；导航顺序固定为项目、帖子类型、QC 要求、文案看板、飞书输出。

- [ ] **Step 5: 实现路由**

路由：`/projects`、`/projects/new`、`/projects/:id/content`、`/projects/:id/types`、`/projects/:id/qc`、`/projects/:id/board`、`/projects/:id/export`。未知路径返回可操作的 404 页面。

- [ ] **Step 6: 验证**

Run: `npm --prefix frontend test -- --run && npm --prefix frontend run typecheck`

Expected: 全部通过。

- [ ] **Step 7: 提交**

```bash
git add frontend/src
git commit -m "feat: add frontend shell and api contracts"
```

## Task 15: 项目列表与项目 Brief 拆解确认界面

**Files:**
- Create: `frontend/src/features/projects/ProjectListPage.tsx`
- Create: `frontend/src/features/projects/NewProjectPage.tsx`
- Create: `frontend/src/features/project-content/ProjectContentPage.tsx`
- Create: `frontend/src/features/project-content/BriefInputPanel.tsx`
- Create: `frontend/src/features/project-content/ParsedSectionEditor.tsx`
- Test: `frontend/src/features/project-content/ProjectContentPage.test.tsx`

- [ ] **Step 1: 写空状态和解析结果测试**

新项目没有默认类型或模板；上传/粘贴二选一；解析后显示项目内容、文案需求、QC 需求、待确认四区。

- [ ] **Step 2: 实现项目列表**

显示名称、品牌/品类、配置状态、最后更新时间和进入按钮；空状态明确提示“新建项目并上传 Brief”。

- [ ] **Step 3: 实现 Brief 输入**

支持拖入或选择 txt/md/docx，但不引入拖拽库；显示文件限制、提取中骨架、失败原因和重试。密钥不出现在页面。

- [ ] **Step 4: 实现可编辑拆解区**

每条 finding 显示值、原文依据、置信度；可新增、编辑、删除和移动分区。缺失字段保持空白，不自动填默认值。

- [ ] **Step 5: 实现明确保存**

未保存修改离开页面时提示；保存成功才更新项目确认状态。不实现复杂自动保存或项目配置版本树。

- [ ] **Step 6: 验证并提交**

Run: `npm --prefix frontend test -- --run ProjectContentPage && npm --prefix frontend run typecheck`

Expected: 全部通过。

```bash
git add frontend/src/features/projects frontend/src/features/project-content
git commit -m "feat: add project brief confirmation ui"
```

## Task 16: 帖子类型组合依据与 QC 规则配置界面

**Files:**
- Create: `frontend/src/features/copy-types/CopyTypesPage.tsx`
- Create: `frontend/src/features/copy-types/CopyTypeEditor.tsx`
- Create: `frontend/src/features/copy-types/ReferenceExamplesEditor.tsx`
- Create: `frontend/src/features/copy-types/TypeConstraintsEditor.tsx`
- Create: `frontend/src/features/qc-rules/QcRulesPage.tsx`
- Create: `frontend/src/features/qc-rules/RuleEditor.tsx`
- Test: `frontend/src/features/copy-types/CopyTypesPage.test.tsx`
- Test: `frontend/src/features/qc-rules/QcRulesPage.test.tsx`

- [ ] **Step 1: 写类型初始空白测试**

首次打开只显示“添加帖子类型”，不渲染种草类型建议或模板入口内容。UI 文案统一使用“帖子类型”。

- [ ] **Step 2: 实现类型编辑器**

字段：名称、数量、类型 Brief、附件和可组合的“参考案例/描述要求”。`template_id/version` 只保留在数据层，P0 不显示模板控件。显示总数量上限和事实冲突提示。

- [ ] **Step 3: 实现参考案例与显式约束编辑**

每个完整案例保留原帖并包含标题、正文和话题；一篇即可分析，最多 5 篇。支持粘贴或上传 txt/md/docx、添加/删除案例、重新分析。右侧展示可编辑风格画像、来源事实和避免照搬表达。描述要求补充标题方向、正文结构、语气、人设、场景和话题；下方固定“一定要有/一定不要有”。界面提示原帖和画像都会进入生成 Prompt，并会进行防照搬 QC。

- [ ] **Step 4: 实现未分类文件区**

逐条显示模型建议类型、依据和置信度；用户手动确认归属，模型建议不自动建立类型。

- [ ] **Step 5: 实现 QC 三栏视图**

硬规则、软规则、待确认三栏；支持项目/类型筛选、编辑、删除、启停。硬规则冲突显示阻断提示，类型软规则覆盖关系显示来源。

未单独填写类型 QC 时，QC 页面自动展示由“一定要有/不要有”生成的默认规则，并标注“来自帖子类型约束”；用户可编辑或停用。显式类型 QC 作为新增规则，不静默覆盖项目硬规则。

- [ ] **Step 6: 实现生成前校验摘要**

在进入看板前展示所有阻断项；“开始生成”只在项目已保存、存在类型、总量有效、无未确认硬冲突，以及所有已启用参考案例的风格画像均确认时启用。

- [ ] **Step 7: 验证并提交**

Run: `npm --prefix frontend test -- --run CopyTypesPage QcRulesPage`

Expected: 全部通过。

```bash
git add frontend/src/features/copy-types frontend/src/features/qc-rules
git commit -m "feat: add copy type and qc rule configuration ui"
```

## Task 17: 五列文案看板与轮询

**Files:**
- Create: `frontend/src/features/board/BoardPage.tsx`
- Create: `frontend/src/features/board/BoardStats.tsx`
- Create: `frontend/src/features/board/BoardColumn.tsx`
- Create: `frontend/src/features/board/CopyItemCard.tsx`
- Create: `frontend/src/features/board/statusPresentation.ts`
- Create: `frontend/src/features/board/useBoardPolling.ts`
- Test: `frontend/src/features/board/BoardPage.test.tsx`

- [ ] **Step 1: 写五列和统计一致性测试**

任何空列也必须显示；AI processing 为两列之和；已完成卡片能区分三种 completion reason。

- [ ] **Step 2: 实现集中状态映射**

状态文案、背景 token、图标、辅助动作全部在 `statusPresentation.ts`，组件中禁止 switch 散落颜色。

- [ ] **Step 3: 实现看板布局**

≥1440px 完整五列；1024–1439 横向滚动；不拖拽。卡片显示 item ID、类型、标题/进度、问题、相似度、修改次数和时间。

- [ ] **Step 4: 实现轮询**

页面可见且存在运行中项目时每 2 秒轮询；页面隐藏后暂停；请求未完成时不叠加下一次；失败保留旧卡片并提供单条重试。

- [ ] **Step 5: 实现筛选和生成批次入口**

筛选保持在 URL query；新批次按钮打开确认框，显示各类型数量和总调用数。

- [ ] **Step 6: 验证并提交**

Run: `npm --prefix frontend test -- --run BoardPage && npm --prefix frontend run typecheck`

Expected: 全部通过。

```bash
git add frontend/src/features/board
git commit -m "feat: add live five-column copy board"
```

## Task 18: 人工审核覆盖面板与定向 AI 修改

**Files:**
- Create: `frontend/src/features/review/ReviewOverlay.tsx`
- Create: `frontend/src/features/review/CopyEditor.tsx`
- Create: `frontend/src/features/review/QcFindingsPanel.tsx`
- Create: `frontend/src/features/review/SelectionRewriteDialog.tsx`
- Create: `frontend/src/features/review/ForcePassDialog.tsx`
- Test: `frontend/src/features/review/ReviewOverlay.test.tsx`

- [ ] **Step 1: 写固定操作顺序测试**

底部依次为保存修改、未通过、强制通过、正常通过；正常通过为 primary；强制通过空遗留问题不能提交。

- [ ] **Step 2: 实现覆盖面板**

桌面宽约 68vw 且最低 960px；左 64% 编辑、右 36% QC；220ms 右侧进入。小屏变全屏纵向布局。

- [ ] **Step 3: 实现可控文本编辑器**

标题与正文使用受控输入，标签使用轻量 chip input。支持 selectionStart/selectionEnd；选区非空显示“让 AI 修改”胶囊，同时监听 contextmenu 和键盘入口。

- [ ] **Step 4: 实现选区改写冲突保护**

提交 expected_version 与 selected_text；409 时保留用户编辑内容并提示重新加载，不自动覆盖。

- [ ] **Step 5: 实现 QC 定位**

finding 的“定位”按钮聚焦对应字段并选中 evidence；无法精确定位时滚动到字段并显示说明，不伪造选区。

- [ ] **Step 6: 实现审核动作**

人工定向 AI 修改完成后刷新 item 并保持面板打开；正常/强制通过后关闭并把卡片移动到已完成；未通过保留在人审栏。

- [ ] **Step 7: 验证并提交**

Run: `npm --prefix frontend test -- --run ReviewOverlay`

Expected: 全部通过。

```bash
git add frontend/src/features/review
git commit -m "feat: add accessible human review workflow"
```

## Task 19: 飞书输出页与只读连接状态

**Files:**
- Create: `frontend/src/features/export/ExportPage.tsx`
- Create: `frontend/src/features/export/ConnectionStatus.tsx`
- Create: `frontend/src/features/export/ExportHistory.tsx`
- Test: `frontend/src/features/export/ExportPage.test.tsx`

- [ ] **Step 1: 写无凭证字段测试**

页面不得出现 app secret、API key 或 spreadsheet token 输入框；只显示“已配置/未配置”。

- [ ] **Step 2: 实现输出预览**

显示将输出的 completed 数量、三种完成方式分布、列名和被排除的待人工/未通过数量。

- [ ] **Step 3: 实现输出与重试**

创建 export run 后轮询状态；失败重试使用原 export ID；若已有 sheet_id，界面说明“将继续写入原子 Sheet”，禁止生成新 ID。

- [ ] **Step 4: 实现历史**

显示 run_id、sheet title、成功行数、状态、时间和安全错误；Fake adapter 明确标记“模拟输出”。

- [ ] **Step 5: 验证并提交**

Run: `npm --prefix frontend test -- --run ExportPage`

Expected: 全部通过。

```bash
git add frontend/src/features/export
git commit -m "feat: add export preview and history ui"
```

## Task 20: 响应式、可访问性与边界状态验收

**Files:**
- Modify: `frontend/src/styles/global.css`
- Modify: relevant frontend components
- Create: `frontend/src/components/Skeleton.tsx`
- Create: `frontend/src/components/EmptyState.tsx`
- Create: `frontend/src/components/ErrorNotice.tsx`
- Test: `frontend/src/app/accessibility.test.tsx`

- [ ] **Step 1: 实现响应式断点**

按视觉规范实现 ≥1440、1024–1439、768–1023、≤767 四档；移动端看板为单列分段控件，不把五列压进屏幕。

- [ ] **Step 2: 实现键盘和焦点**

所有图标按钮有 aria-label；任务卡可聚焦；对话框有焦点圈定和 Escape；关闭后焦点回触发按钮；focus-visible 使用指定 token。

- [ ] **Step 3: 实现加载、空状态和错误**

骨架替代空白 spinner；每个空状态说明下一步；API 错误保留现有数据和编辑文本，并提供单条重试。

- [ ] **Step 4: 尊重减少动效**

`prefers-reduced-motion: reduce` 下关闭位移，只保留即时显示；禁止弹跳和宽高动画。

- [ ] **Step 5: 运行前端测试**

Run: `npm --prefix frontend test -- --run && npm --prefix frontend run typecheck && npm --prefix frontend run build`

Expected: 全部通过。

- [ ] **Step 6: 提交**

```bash
git add frontend/src
git commit -m "fix: complete responsive and accessible states"
```

## Task 21: 端到端验收夹具与完整流程

**Files:**
- Create: `examples/demo-project-brief.md`
- Create: `examples/demo-type-brief.md`
- Create: `examples/demo-project-qc.md`
- Create: `e2e/playwright.config.ts`
- Create: `e2e/specs/happy-path.spec.ts`
- Create: `e2e/specs/exception-review.spec.ts`

- [ ] **Step 1: 创建虚构快消演示数据**

使用虚构“清爽气泡水”项目，包含品牌、SKU、人群、场景、产品事实、事实依据、禁止宣称；类型 Brief 只定义用户自建类型，不写入系统模板。

- [ ] **Step 2: 写 AI 直通 E2E**

创建项目 → 解析并保存 Brief → 新增类型 → 添加 QC → 生成 → 等待 AI QC → 断言卡片直接进入已完成且标为 AI 自动通过。

- [ ] **Step 3: 写爆款参考建立类型 E2E**

新增帖子类型 → 勾选参考案例与描述要求 → 输入多篇配对原帖/标题/正文/话题 → AI 生成风格画像 → 确认来源事实不进入项目 → 填写“一定要有/不要有”且不单独添加类型 QC → 确认默认 QC 自动出现 → 生成 → 断言运行快照和模型请求同时含原帖与画像，输出满足约束且不触发参考照搬相似度阈值。

- [ ] **Step 4: 写异常人工审核 E2E**

使用 `[FAIL_QC]` 夹具 → 自动修改耗尽 → 进入人工审核 → 直接编辑仍留在人审 → 选区 AI 修改后返回人审 → 正常通过进入完成。

- [ ] **Step 5: 写强制通过 E2E**

空遗留问题提交被阻止；自动带入未解决问题；补充理由后完成并标记“强制通过 · 有遗留问题”。

- [ ] **Step 6: 写输出幂等 E2E**

Fake exporter 首次成功创建一个 sheet；同 export ID 重试不增加 sheet；未完成项不在输出预览和行数据中。

- [ ] **Step 7: 运行 E2E**

Run: `npm --prefix frontend run test:e2e`

Expected: 所有 Chromium 用例通过，失败时保留截图和 trace。

- [ ] **Step 8: 提交**

```bash
git add examples e2e
git commit -m "test: cover end-to-end copy qc workflow"
```

## Task 22: 打包、Windows 启动与文档收口

**Files:**
- Modify: `backend/app/main.py`
- Modify: `README.md`
- Create: `scripts/dev.ps1`
- Create: `scripts/build.ps1`
- Create: `scripts/start.ps1`
- Modify: `docs/external-integration-contract.md`
- Test: `backend/tests/integration/test_static_app.py`

- [ ] **Step 1: 构建前端并由 FastAPI 托管**

生产模式将 `frontend/dist` 挂载为静态资源；`/api/*` 永远优先；SPA 未知前端路由回退 `index.html`，不存在的 API 仍返回 JSON 404。

- [ ] **Step 2: 编写 PowerShell 脚本**

- `dev.ps1`：并行启动 FastAPI 与 Vite，失败时退出并保留日志。
- `build.ps1`：运行测试、类型检查、前端构建。
- `start.ps1`：检查 `.env` 和数据库目录后启动单个 Uvicorn 服务。

- [ ] **Step 3: 更新 README**

包含 Windows 安装、`.env` 复制、Fake Adapter 演示、数据库备份、允许文件格式、状态机、测试命令、真实 API 接入边界和故障恢复。

- [ ] **Step 4: 编写外部接入契约**

核对模型六个方法的请求/返回 Pydantic schema、超时/错误映射、幂等要求；列出飞书三项环境变量、create/write 两步协议、固定列和 sheet 重试规则。不得猜测未提供的供应商 URL。

- [ ] **Step 5: 执行完整验收**

Run:

```powershell
python -m pytest backend/tests -q
python -m ruff check backend
npm --prefix frontend test -- --run
npm --prefix frontend run typecheck
npm --prefix frontend run build
npm --prefix frontend run test:e2e
```

Expected: 全部退出码为 0；无网络时 Fake Adapter 流程完整可用。

- [ ] **Step 6: 安全检查**

确认 `.env`、SQLite 数据库、上传文件、Playwright trace 不入 Git；API 响应和日志不包含 secret；前端 bundle 中搜索不到 `.env` 秘密值。

- [ ] **Step 7: 提交**

```bash
git add README.md scripts backend/app/main.py backend/tests/integration/test_static_app.py docs/external-integration-contract.md
git commit -m "docs: finalize local mvp delivery workflow"
```

## 5. CLIPROXY 与飞书实网验证门槛

核心长任务会同时实现 Fake Adapter 与经过 MockTransport 合同测试的 `CliProxyModelAdapter`。没有密钥时使用 Fake 完整验收；获得以下 `.env` 信息后执行实网 smoke test。只有实际协议偏离 Responses 兼容形式时才修改 CLIPROXY Adapter，业务流程不变。

### 模型

- `CLIPROXY_BASE_URL`。
- `CLIPROXY_API_KEY`。
- `CLIPROXY_GENERATION_MODEL` 与 `CLIPROXY_QC_MODEL`。
- 实际 endpoint、Responses 返回样例及结构化 JSON 能力。
- 请求/返回样例。
- 并发、频率、超时和 token 限制。

### 飞书

- `FEISHU_APP_ID`。
- `FEISHU_APP_SECRET`。
- `FEISHU_SPREADSHEET_TOKEN`。
- 应用是否已有电子表格读取、创建子 Sheet、写单元格权限。
- API 的实际错误码和限流策略。

CLIPROXY 实网结果必须继续通过 Task 5 schema；飞书真实适配器必须通过 Task 13 contract tests。业务服务与前端不得因供应商差异修改状态字段。

## 6. 最终验收清单

- [ ] 新项目没有默认类型或模板。
- [ ] 帖子类型可只用参考案例、只用描述要求或组合两者；一篇爆款案例即可生成可编辑风格画像。
- [ ] 每类型支持 1–5 篇参考帖，原帖全文、标题、正文和话题完整保存并进入生成 Prompt；来源事实不进入当前项目。
- [ ] 生成 Prompt 同时包含原帖、确认画像和禁止继承/照搬分区，生成稿会检查与各案例的相似度。
- [ ] “一定要有/一定不要有”作为显式类型约束执行；未另填类型 QC 时自动成为可编辑默认 QC，但不能覆盖项目硬规则。
- [ ] Brief 缺失信息不会被 Fake/真实适配器补写；不确定内容进入待确认。
- [ ] 项目和类型 Brief 的拆解结果可编辑并明确保存。
- [ ] 项目硬规则不能被类型覆盖；软规则覆盖有来源可查。
- [ ] 每条成稿具有稳定 item ID 和不可变版本历史。
- [ ] AI QC 通过直接完成，不经过人工审核。
- [ ] 自动 AI 修改后重新 QC；人工定向修改后返回人工审核。
- [ ] 看板只有五列，没有“一轮/二轮”或拖拽。
- [ ] 五列数量与统计卡始终一致。
- [ ] API 失败保留文案与卡片，可单条重试。
- [ ] 普通通过不能带未解决硬规则。
- [ ] 强制通过遗留问题必填且自动带入未解决问题。
- [ ] 飞书/模拟输出只选择 completed 项。
- [ ] 同一 export run 重试不重复创建子 Sheet。
- [ ] `.env` 秘密不进入前端、日志或 Git。
- [ ] 桌面、平板和移动端符合视觉规范 v0.1。
- [ ] 键盘、焦点、对比度、空状态和减少动效通过验收。
- [ ] 所有 pytest、前端单测、类型检查、构建和 Playwright 用例通过。

## 7. 长任务启动点

下一次长任务从 **Task 1** 开始，严格按任务顺序执行。每完成一项：

1. 运行该任务指定测试。
2. 更新根目录 `progress.md`。
3. 将 `task_plan.md` 对应实施阶段标记为进行中或完成。
4. 检查 `git diff`，只提交本任务范围。
5. 通过后再进入下一任务。

在 CLIPROXY `.env` 与飞书信息缺失期间，执行到 Task 22 仍可交付完整的本地 Fake Adapter MVP 和经过模拟 HTTP 测试的 CLIPROXY Adapter；不要在长任务中填入或猜测真实秘密值。
