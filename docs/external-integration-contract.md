# 外部模型与飞书接入契约 v0.1

## 1. 目的

核心产品不依赖具体模型供应商或飞书 SDK。真实能力后续通过 `.env` 和适配器接入；适配器必须满足本契约，不能改变业务状态机、数据库字段或前端流程。

当前不记录真实 URL、密钥或电子表格标识。

## 2. 环境变量

```dotenv
# 通用
APP_ENV=development
DATABASE_PATH=./data/batch-copy-qc.sqlite3
UPLOAD_DIR=./data/uploads

# 模型：开发可使用 fake，真实环境使用 cliproxy
MODEL_ADAPTER=fake
CLIPROXY_BASE_URL=
CLIPROXY_API_KEY=
CLIPROXY_GENERATION_MODEL=
CLIPROXY_QC_MODEL=
CLIPROXY_REASONING_EFFORT=medium
MODEL_CONCURRENCY=2
CLIPROXY_TIMEOUT_SECONDS=120
AUTO_REWRITE_LIMIT=1
API_RETRY_LIMIT=2
SIMILARITY_THRESHOLD=85
QC_CONFIDENCE_THRESHOLD=0.70

# 飞书
FEISHU_ADAPTER=unconfigured
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_SPREADSHEET_TOKEN=
```

规则：

- `.env` 不提交 Git。
- 后端只返回 `configured: true/false` 和非敏感 adapter/model 名称。
- 前端不提供 API key、app secret 或 spreadsheet token 输入框。
- 日志与错误详情必须脱敏 Authorization、Cookie、secret 和 token。

## 3. 模型适配器

模型供应商固定为 CLIPROXY。`CliProxyModelAdapter` 使用 OpenAI Responses 兼容请求形式：Bearer 鉴权，请求写入 `model`、`instructions`、`input`、`max_output_tokens` 和可选 `reasoning.effort`；响应兼容顶层 `output_text` 及 `output[].content[].text`。任何供应商原始 JSON 都必须先转换成项目内部 Pydantic 类型。

适配器提供六个异步方法：

| 方法 | 输入 | 输出 | 幂等与约束 |
|---|---|---|---|
| `parse_brief` | 原文、scope、可选来源名 | 四区结构化 finding | 不补写原文缺失事实；每条有依据与置信度 |
| `analyze_reference_examples` | 一至五篇完整参考案例（标题、正文、话题） | 可编辑的参考风格画像、来源事实、避免照搬表达 | 不创建当前项目事实 |
| `generate_copy` | 项目事实、原参考案例全文、参考风格画像、描述要求、一定要有/不要有、有效规则、槽位 ID | 标题、正文、标签 | Prompt 必须声明项目事实唯一、来源事实禁用、原句禁抄；相同 idempotency key 不重复计费或由服务端去重 |
| `run_semantic_qc` | 当前版本、事实、规则、批次相似上下文 | findings、置信度 | 不直接修改文案或决定强制通过 |
| `rewrite_copy` | 当前版本、需修复 findings、硬规则 | 完整新稿 | 只修复指定问题，不新增事实 |
| `rewrite_selection` | 字段、选中文字、上下文、人工方向 | 替换文字 | 只返回替换片段，不返回整篇文案 |

统一错误分类：

- `MODEL_AUTH_FAILED`：不自动重试，连接状态标为异常。
- `MODEL_RATE_LIMITED`：遵守 Retry-After，技术重试最多 2 次。
- `MODEL_TIMEOUT`：技术重试最多 2 次。
- `MODEL_RESPONSE_INVALID`：不覆盖现有内容；转人工或标记 Brief 解析失败。
- `MODEL_UNAVAILABLE`：保留任务与数据，可单条重试。

结构化返回必须经过 Pydantic 严格校验；供应商原始响应不得直接进入数据库业务 JSON。

## 4. 飞书输出适配器

一个项目使用 `.env` 指定的一份电子表格；每个 export run 新建一个子 Sheet。

适配器方法：

1. `create_run_sheet(export_run_id, sheet_title) -> sheet_id`
2. `write_rows(sheet_id, rows) -> None`

固定列：

```text
序号 | item_id | 文案类型 | 标题 | 正文 | 话题标签 | 完成方式 | 遗留问题 | 修改说明
```

输出范围：

- 只输出 `workflow_status=completed`。
- 完成方式为 AI 自动通过、人工通过或强制通过。
- 强制通过必须写入遗留问题。
- 未通过、待人工审核和运行中的条目不进入正式子 Sheet。

幂等规则：

- `export_run_id` 是客户端与服务端共同幂等键。
- 本地已有 `sheet_id` 时，失败重试不得再次创建 Sheet。
- 写入采用固定表头和确定行顺序；重试覆盖同一目标范围，不做末尾盲目追加。
- 已成功 export run 再次请求返回原结果。
- 文案在成功输出后又被召回、编辑并重新完成时，创建新的 export run 和新子 Sheet。

统一错误分类：

- `FEISHU_NOT_CONFIGURED`
- `FEISHU_AUTH_FAILED`
- `FEISHU_PERMISSION_DENIED`
- `FEISHU_RATE_LIMITED`
- `FEISHU_SHEET_CREATE_FAILED`
- `FEISHU_ROWS_WRITE_FAILED`

飞书错误不能触发重新生成或重新 QC。

## 5. 接入前所需资料

模型：CLIPROXY Base URL、API Key、生成/QC 模型名、实际请求/响应样例、结构化输出能力、并发与频率限制。若实际 endpoint 或字段与 Responses 兼容形式不同，只修改 `CliProxyModelAdapter`。

飞书：App ID、App Secret、Spreadsheet Token、实际权限范围、限流和错误码说明。

## 6. 合同测试

真实适配器接入时必须复用 Fake Adapter 的 contract tests：

- 六个模型操作都能解析成约定的 Pydantic 类型。
- 超时、限流、鉴权失败和无效响应映射到固定错误码。
- 不记录秘密或供应商原始错误 body。
- 飞书首次创建一次 Sheet；已有 sheet ID 的重试不再次创建。
- 写入行数与 completed 项数相等，列顺序固定。
- 适配器替换后前端 API response schema 无变化。
