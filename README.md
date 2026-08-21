# 小红书快消种草批量文案 QC

一个轻量、独立的本地产品：把项目 Brief 拆成可编辑事实和规则，由用户建立空白帖子类型或提供 1–5 篇爆款参考，批量生成文案，完成确定性 + 模型 QC、异常人工审核，并把已完成结果写入飞书电子表格的新子 Sheet。

首版目标是把流程、审计和外部适配边界搭稳。内容质量的持续优化属于后续 P1。

## 已实现流程

1. 建立项目，粘贴或上传项目 Brief。
2. AI 把原文拆为项目内容、文案需求、QC 要求和待确认项；用户逐项编辑后确认。
3. 用户从空白建立帖子类型，可输入类型 Brief、描述要求，或录入 1–5 篇爆款参考帖。
4. 原帖全文与用户确认的风格画像都进入生成 Prompt；来源事实不得成为项目事实，并执行 RapidFuzz 防照搬检查。
5. 项目级和类型级 QC 分硬规则、软规则和待确认项；项目硬规则不可覆盖。
6. 每次生成按项目自动编号为第 1、2、3…批；看板一次只展示一个批次，旧批次可整批隐藏或恢复而不删除历史。
7. 生成后进入五列看板：待 AI QC、AI QC 中、AI 修改中、待人工审核、已完成。
8. AI QC 通过直接完成；自动修改后重新 AI QC；人工选区修改后返回人工审核。
9. 人工可直接编辑、正常通过、未通过或强制通过；强制通过必须留下非空遗留问题。
10. 飞书只输出当前批次的已完成项；每个 export run 创建一个子 Sheet，失败重试保持幂等。

## 技术栈

- 前端：React 19、TypeScript、Vite
- 后端：Python 3.12、FastAPI、Pydantic
- 持久化：SQLite
- 文本相似度：RapidFuzz
- 模型：CLIPROXY Responses 兼容适配器 + 本地 Fake Adapter
- 输出：飞书开放平台适配器 + Fake Exporter

## Windows 快速开始

要求：Python 3.12、Node.js 20+、npm。

```powershell
cd E:\xixiAi\batch-copy-qc
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
npm.cmd --prefix frontend install
Copy-Item .env.example .env
```

首次建议保留 `.env` 中的 `MODEL_ADAPTER=fake` 和 `FEISHU_ADAPTER=fake`，无需联网即可体验完整流程。

开发模式（FastAPI 8000 + Vite 5173）：

```powershell
.\scripts\dev.ps1
```

构建并以单进程运行：

```powershell
.\scripts\build.ps1
.\scripts\start.ps1
```

打开 [http://127.0.0.1:8000](http://127.0.0.1:8000)。生产启动固定为一个 Uvicorn worker；当前飞书 export run 的创建锁以单进程为产品边界。

## `.env` 接入

真实秘密只写入本地 `.env`，不得写入前端、文档、日志或 Git。

CLIPROXY 必填项：

```dotenv
MODEL_ADAPTER=cliproxy
CLIPROXY_BASE_URL=
CLIPROXY_API_KEY=
CLIPROXY_GENERATION_MODEL=
CLIPROXY_QC_MODEL=
CLIPROXY_API_MODE=responses
```

`responses` 是严格默认；`auto` 只在 404/405/501 时回退 Chat；`chat` 用于明确只支持旧协议的网关。

飞书可使用电子表格 token，或用户提供的 Wiki 节点 token：

```dotenv
FEISHU_ADAPTER=feishu
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_SPREADSHEET_TOKEN=
FEISHU_WIKI_NODE_TOKEN=
```

Wiki 节点必须指向电子表格。前端仅显示连接是否已配置，不显示任何凭证。详细协议见 [外部接入契约](docs/external-integration-contract.md)。

## 演示材料

- [项目 Brief](examples/demo-project-brief.md)
- [帖子类型 Brief](examples/demo-type-brief.md)
- [项目 QC](examples/demo-project-qc.md)

系统支持 `.txt`、`.md`、`.docx`，单文件最大 10MB；项目附件最多 20 个。当前不做 OCR。

## 测试

```powershell
py -3.12 -m pytest backend/tests -q -p no:cacheprovider
py -3.12 -m ruff check backend
npm.cmd --prefix frontend test -- --run
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test:e2e
```

E2E 使用 Fake Adapter，不会调用真实模型或写入飞书。真实连接只执行单独 smoke test。

当前实网验证边界：CLIPROXY 只完成 `parse_brief` 的 Responses 最小调用；其余生成、语义 QC、完整改写、选区改写与参考画像分析尚未做实网 smoke test。飞书只完成 tenant 鉴权、Wiki→Sheet 解析和工作表列表读取；尚未在真实表格创建子 Sheet 或写入数据。合同与 MockTransport 测试已覆盖这些操作，但不能替代实网验证。

## 数据、备份与恢复

- 默认数据库：`data/batch-copy-qc.sqlite3`
- 默认上传目录：`data/uploads/`
- 在服务停止后，复制数据库文件和上传目录即可做一致性备份。
- SQLite 的 `-wal`、`-shm` 临时文件也在 Git 忽略范围内。
- 技术失败会保留卡片、版本和用户编辑，可单条重试；飞书失败不会重新生成或重新 QC。
- export run 成功后再次编辑文案，应新建 export run 和新子 Sheet，不修改历史 Sheet。

## 关键文档

- [产品短策划](docs/brief-proposal.md)
- [技术选型](docs/tech-stack-selection.md)
- [前端视觉规范](docs/frontend-visual-spec-v0.1.md)
- [完整实施计划](docs/superpowers/plans/2026-08-21-batch-copy-qc-mvp.md)
- [终审检查表](docs/implementation-review-checklist.md)
