# 小红书快消种草批量文案与 QC MVP｜终审检查表

> 版本：v0.1
> 建立时间：2026-08-21
> 适用范围：`E:\xixiAi\batch-copy-qc` P0 MVP 代码完成后的独立终审
> 基线文件：`task_plan.md`、`docs/superpowers/plans/2026-08-21-batch-copy-qc-mvp.md`、`docs/external-integration-contract.md`、`docs/frontend-visual-spec-v0.1.md`

## 0. 使用规则与终审结论

### 0.1 记录格式

每项只允许填写以下一种结论：

- `[x] PASS`：已有可复核证据，且行为与基线一致。
- `[ ] FAIL`：已验证不符合，必须记录缺陷编号、复现步骤和影响。
- `[ ] BLOCKED`：受缺失凭证、外部权限或环境阻塞，必须记录阻塞条件；不得写成 PASS。
- `[ ] N/A`：仅限基线明确不适用的项目，必须说明原因。

每一项终审记录至少包含：

```text
结论：PASS / FAIL / BLOCKED / N/A
证据：测试名、命令输出、API 请求/响应摘要、数据库查询、截图或文件位置
备注：缺陷编号、风险、阻塞条件或不适用理由
```

### 0.2 证据规则

- 不以“代码看起来正确”代替运行证据；关键不变量必须同时有自动测试和必要的手工验证。
- 不以 Fake Adapter、MockTransport 或前端模拟数据代替 CLIPROXY/飞书实网结果。
- 截图不得包含 API Key、App Secret、Spreadsheet Token、Authorization、Cookie 或真实 Brief 敏感内容。
- 测试命令需记录退出码、通过/失败数量和执行日期；不得只粘贴截断后的绿色界面。
- 数据库检查优先使用一次性测试数据库；不得破坏用户现有项目或真实飞书数据。
- 终审发现的问题必须按 P0/P1/P2 标级；P0 未清零不得给出“可交付”。

### 0.3 停发条件

以下任一情况存在即判定 P0 FAIL，产品不得宣称完成：

- 存在非法状态跳转、状态与完成原因不一致、并发覆盖或重启后重复生成。
- 项目硬规则可被类型规则覆盖，或普通通过能绕过未解决硬规则。
- 参考原帖未进入生成 Prompt，或参考来源事实可能进入项目事实/生成事实。
- 未执行防照搬检查，或高度相似原帖仍可 AI 自动通过。
- 强制通过允许空遗留问题，或审计记录无法追溯。
- 同一 export run 重试创建多个飞书子 Sheet，或未完成项进入正式输出。
- Secret 出现在 Git、前端 bundle、API 响应、日志、错误详情、截图或测试产物中。
- SQLite 不是唯一权威存储，关键审计记录可被覆盖，或外键/唯一/状态约束失效。
- 前后端 API 枚举、错误格式或关键字段不一致，导致状态或数据被错误解释。
- 五列看板状态映射错误、统计不守恒，或移动端/键盘无法完成关键审核流程。
- 必需自动测试失败；已配置真实外部服务却未做实网 smoke test，仍声称实网接入完成。

### 0.4 最终结论模板

- [ ] **可交付**：所有 P0 通过；实网项已 PASS，或明确声明仅交付 Fake/合同测试版本。
- [ ] **有条件可交付**：本地 MVP 全部通过，但实网因凭证/权限 BLOCKED；产品文档不得声称真实接入已验证。
- [ ] **不可交付**：存在任一 P0 FAIL，或关键证据缺失。

---

## 1. 范围、架构与构建边界

- [ ] **ARCH-01 独立产品边界（P0）**：仓库根目录为 `batch-copy-qc`；父目录或其他产品未被纳入版本控制、运行依赖或写入范围。
- [ ] **ARCH-02 技术栈一致（P1）**：前端为 React + TypeScript + Vite；后端为 Python 3.12 + FastAPI + Pydantic v2；持久化为 SQLite；相似度使用 RapidFuzz。
- [ ] **ARCH-03 轻量单体（P1）**：未引入 Celery、Redis、RabbitMQ、LangGraph、外部数据库、重量级拖拽库或富文本编辑器。
- [ ] **ARCH-04 P0 边界（P1）**：无内置模板/模板市场、PDF/Excel/OCR、图片生成、自动发布、多用户权限或云端协作；`template_id/template_version` 仅存在数据边界，前端不展示模板控件。
- [ ] **ARCH-05 SQLite 权威性（P0）**：项目配置、版本、QC、审核、输出记录以 SQLite 为唯一权威；Fake 输出或 CSV/JSON 不形成第二权威数据源。
- [ ] **ARCH-06 适配器隔离（P0）**：切换 Fake/CLIPROXY 或 Fake/飞书适配器不改变业务状态、数据库字段和前端 API schema。
- [ ] **ARCH-07 Windows 可运行（P0）**：Windows 环境按 README 可安装、构建、启动；PowerShell 脚本失败时返回非零退出码并保留安全日志。
- [ ] **ARCH-08 静态托管（P1）**：生产构建由 FastAPI 托管；`/api/*` 优先，未知 SPA 路由返回 `index.html`，不存在 API 返回 JSON 404。

## 2. 状态机与并发不变量

### 2.1 枚举与状态表示

- [ ] **STATE-01 固定状态集合（P0）**：`workflow_status` 只允许 `pending_ai_qc`、`ai_qc_running`、`ai_rewrite_running`、`human_review`、`completed`。
- [ ] **STATE-02 完成原因分离（P0）**：`completion_reason` 只允许 `ai_pass`、`human_pass`、`forced_pass`，且不被混入 `workflow_status`。
- [ ] **STATE-03 完成不变量（P0）**：`completed` 必须有 completion reason；非 `completed` 必须没有 completion reason；数据库写入和 API 均无法构造反例。
- [ ] **STATE-04 人审处置分离（P1）**：`review_disposition` 只表达 `open/rejected`；“未通过”保持 `human_review`，不伪装为完成状态。
- [ ] **STATE-05 前后端枚举一致（P0）**：Python 枚举、SQLite CHECK、Pydantic schema、TypeScript union 和 UI 映射完全一致。

### 2.2 合法转换

- [ ] **STATE-06 生成入口（P0）**：生成成功后只进入 `pending_ai_qc`，不会跳过 QC。
- [ ] **STATE-07 AI QC 运行（P0）**：`pending_ai_qc → ai_qc_running` 原子执行，重复 worker/轮询不会并发运行同一 item。
- [ ] **STATE-08 AI 直通（P0）**：全部 QC 通过时进入 `completed/ai_pass`，无需人工审核，并产生系统审核事件。
- [ ] **STATE-09 自动改写循环（P0）**：仅全部问题可自动修复且未超限时进入 `ai_rewrite_running`；成功写新版本后回到 `pending_ai_qc` 并重新执行完整 QC。
- [ ] **STATE-10 异常转人工（P0）**：硬规则冲突、事实不确定、参考相似度风险、低置信度、自动次数耗尽和 API 最终异常进入 `human_review`。
- [ ] **STATE-11 直接编辑（P0）**：人工直接编辑生成新版本后仍为 `human_review`，不会自动完成。
- [ ] **STATE-12 人工定向改写（P0）**：`human_review → ai_rewrite_running(origin=human) → human_review`；不得回 AI 自动直通路径。
- [ ] **STATE-13 普通通过（P0）**：只有无未解决硬规则时可进入 `completed/human_pass`。
- [ ] **STATE-14 强制通过（P0）**：仅从 `human_review` 且遗留问题非空时进入 `completed/forced_pass`。
- [ ] **STATE-15 未通过（P0）**：reject 记录原因，保持 `human_review/rejected`，不能进入正式输出。
- [ ] **STATE-16 召回（P0）**：recall 将 completed item 召回 `human_review`、清空当前 completion reason，同时保留原完成事件和旧版本。
- [ ] **STATE-17 非法转换拒绝（P0）**：所有非法事件返回 `ITEM_TRANSITION_INVALID`，不产生部分写入。

### 2.3 原子性、幂等与恢复

- [ ] **STATE-18 乐观并发（P0）**：人工编辑和选区改写提交 `expected_version`；版本冲突返回 409，服务端和前端均不覆盖用户新内容。
- [ ] **STATE-19 状态 CAS（P0）**：状态更新校验预期旧状态；重复回调、重复轮询或多个 worker 不会覆盖更新。
- [ ] **STATE-20 事务边界（P0）**：版本、QC run/findings、审核事件和状态变更在合理的单一事务内提交；失败时全部回滚。
- [ ] **STATE-21 重启恢复（P0）**：进程重启后中断的 running 工作恢复排队；成功 item 不重复生成，稳定 item ID 和历史版本不变。
- [ ] **STATE-22 技术重试（P1）**：网络错误按配置最多重试，尊重 Retry-After，退避不超过计划上限；业务重写次数与技术重试次数分开统计。
- [ ] **STATE-23 单条重试约束（P0）**：只有具备可重试系统错误原因的 `human_review` item 可回 `pending_ai_qc`；人工 reject 不得借此进入自动流程。

## 3. 项目、Brief 与帖子类型

- [ ] **BRIEF-01 无预设类型（P0）**：新项目帖子类型列表为空；不存在默认类型、示例类型或模板推荐。
- [ ] **BRIEF-02 项目 Brief 输入（P0）**：粘贴与文件上传严格二选一；支持 `.txt/.md/.docx`，P0 明确拒绝 PDF/Excel/图片。
- [ ] **BRIEF-03 四区拆解（P0）**：结果包含项目内容、文案需求、QC 需求、待确认；每条包含 value、原文依据、置信度和 section。
- [ ] **BRIEF-04 不补写事实（P0）**：原文缺失信息保持空白；冲突和不确定内容进入待确认，不被 Fake 或真实模型擅自补齐。
- [ ] **BRIEF-05 可视化确认（P0）**：用户能新增、编辑、删除、移动 finding；明确保存前不更新项目确认状态，离开未保存页面有提示。
- [ ] **BRIEF-06 不覆盖已确认内容（P0）**：重新解析只返回 `suggested_changes/conflicts`；未经用户确认不覆盖项目结构化数据。
- [ ] **BRIEF-07 类型 Brief（P0）**：每个用户自建类型可粘贴或上传独立 Brief，使用同类拆解/确认流程。
- [ ] **BRIEF-08 类型事实隔离（P0）**：类型 Brief 中的项目事实只成为“建议更新项目内容”或“事实冲突”；确认前不写入项目事实。
- [ ] **BRIEF-09 类型数量约束（P0）**：单类型数量 1–100，项目全部类型合计不超过 100；启动生成前服务端再次校验。
- [ ] **BRIEF-10 输入模式（P0）**：类型可只用参考案例、只用描述要求或组合使用；至少一种模式有实际内容。
- [ ] **BRIEF-11 未分类文件（P1）**：模型只返回建议类型、依据和置信度；不自动建类型或确认归属。
- [ ] **BRIEF-12 文件安全（P0）**：磁盘使用 UUID 文件名、保留安全显示名；拒绝路径分隔符、空文件、单文件大于 10MB、项目附件超过 20。
- [ ] **BRIEF-13 原子文件保存（P0）**：临时写入成功后原子移动；解析失败保留 `parse_status=failed` 和安全错误码，不暴露堆栈。
- [ ] **BRIEF-14 文本提取（P1）**：UTF-8/BOM、DOCX 段落与表格、CRLF/空行/NUL 归一化符合计划；空文本返回 `BRIEF_TEXT_EMPTY`。

## 4. 参考原帖、事实隔离与防照搬

### 4.1 原帖和风格画像

- [ ] **REF-01 案例数量与完整性（P0）**：每类型支持 1–5 篇；第 6 篇被拒绝；每篇 raw_text、标题、正文和话题相互配对并完整保存。
- [ ] **REF-02 画像确认门槛（P0）**：AI 输出的标题钩子、开头、结构节拍、视角、语气、人设、场景、信息密度、卖点顺序、结尾和标签策略均可编辑；未确认画像不能生成。
- [ ] **REF-03 来源事实识别（P0）**：参考案例中的品牌、价格、功效、规格等写入 `source_facts_to_exclude`，不会进入项目 requirements 或项目事实。
- [ ] **REF-04 避免照搬表达（P0）**：画像明确产出 `phrases_not_to_copy/避免照搬表达`，用户可见、可编辑。

### 4.2 Prompt 进入与事实防火墙

- [ ] **REF-05 原帖确实进入 Prompt（P0）**：通过 Fake 捕获、MockTransport 或安全调试钩子证明 1–5 篇原帖全文和已确认画像同时进入 `generate_copy` 请求。
- [ ] **REF-06 Prompt 分区（P0）**：至少存在明确的 `PROJECT_FACTS`、`REFERENCE_EXAMPLES`、`SOURCE_FACTS_TO_EXCLUDE`、`PHRASES_NOT_TO_COPY` 语义分区。
- [ ] **REF-07 唯一事实源声明（P0）**：Prompt 明确声明项目事实为唯一事实来源；参考帖只学习写法，禁止继承来源品牌、价格、功效和其他事实。
- [ ] **REF-08 快照一致性（P0）**：generation run 保存项目、类型、规则、画像和原帖快照；运行后编辑配置不会改变已启动批次的 Prompt 上下文。
- [ ] **REF-09 改写事实稳定（P0）**：自动整稿改写和人工选区改写都不得引入参考来源事实或新项目事实。

### 4.3 防照搬 QC

- [ ] **REF-10 归一化（P1）**：相似度比较使用 Unicode NFKC、统一空白并忽略无意义标点差异；保存原文不变。
- [ ] **REF-11 多维相似度（P0）**：标题、开头 80 字和全文分别比较，保存最大风险分、来源种类和匹配 ID。
- [ ] **REF-12 参考原帖比较（P0）**：每条生成稿与其类型的全部参考案例比较；不会把 item 与自身比较。
- [ ] **REF-13 批内去重（P0）**：批次近似文案成对检测，只默认标记较后生成 item，以最少改写为原则并展示 matched item。
- [ ] **REF-14 高风险处置（P0）**：命中来源品牌、价格、功效、独特原句或超过相似度阈值会产生可定位 finding，不能 AI 自动通过。
- [ ] **REF-15 修复后复检（P0）**：防照搬自动改写保持项目事实，并在新版本上重新执行参考相似度和其他 QC。

## 5. Hard/Soft 规则与 QC 编排

### 5.1 规则数据与合并

- [ ] **RULE-01 规则字段（P0）**：规则具有 scope、level、category、statement、source_kind/source_evidence、enabled 和正确的 project/type 归属。
- [ ] **RULE-02 项目硬规则不可覆盖（P0）**：任何类型 hard/soft、描述要求、画像或 must/avoid 都不能覆盖项目 hard rule。
- [ ] **RULE-03 软规则覆盖（P0）**：同 category 的类型 soft rule 可覆盖项目 soft rule；有效规则和被覆盖来源均可追溯、可展示。
- [ ] **RULE-04 硬冲突阻断（P0）**：类型要求与项目 hard rule 冲突时进入待确认/阻断；未确认冲突不能启动生成。
- [ ] **RULE-05 启停生效（P1）**：disabled 规则不进入生成/QC，上层来源仍保留；重新启用后恢复。
- [ ] **RULE-06 显式约束（P0）**：“一定要有/一定不要有”作为类型显式约束进入生成和确定性 QC，优先于推断画像但低于项目 hard rule。
- [ ] **RULE-07 派生默认 QC（P0）**：没有 `explicit_type_qc` 时，must/avoid 自动物化为可见可编辑的 `derived_type_constraint`；后来新增显式 QC 不会静默删除派生规则。

### 5.2 确定性、语义与相似度 QC

- [ ] **QC-01 执行顺序（P0）**：每轮先确定性规则和相似度，再运行语义 QC；所有结果绑定当前 item version。
- [ ] **QC-02 最小确定性规则（P0）**：检查标题/正文/标签非空、长度、must/avoid、必含词、禁用词、标签格式和可程序验证的产品事实 hard rule。
- [ ] **QC-03 Finding 完整（P0）**：每项包含 rule_id、level、category、status/message、evidence、suggestion、auto_fixable 和 confidence；规则来源可追溯。
- [ ] **QC-04 语义 QC 边界（P0）**：模型返回严格 schema 的 findings 和置信度；不直接修改文案、不决定强制通过。
- [ ] **QC-05 自动修复资格（P0）**：只有全部未通过项都明确 `auto_fixable=true` 且不含 hard/事实/相似度决策时才自动改写。
- [ ] **QC-06 低置信度（P0）**：低于 `QC_CONFIDENCE_THRESHOLD` 时不自动放行或自动猜测，进入人工审核。
- [ ] **QC-07 自动次数（P0）**：达到 `AUTO_REWRITE_LIMIT` 后不再调用模型，进入人工审核；计数持久化并在 UI 显示。
- [ ] **QC-08 API 失败保留内容（P0）**：模型错误不覆盖现有文案或 QC 记录；卡片保留并显示安全错误码，可按规则单条重试。

## 6. 生成、版本与审计链

- [ ] **GEN-01 运行前校验（P0）**：阻止未保存项目、空类型、数量越界、缺产品事实、未确认 hard 冲突、启用参考但画像未确认；一次返回全部阻断项。
- [ ] **GEN-02 稳定 item ID（P0）**：每个槽位预建稳定 UUID；重试、改写、QC、审核和输出始终引用同一 `item_id`。
- [ ] **GEN-03 槽位唯一（P0）**：`(run_id, copy_type_id, ordinal)` 唯一；失败槽位单独重试不会重建成功 item。
- [ ] **GEN-04 不可变版本（P0）**：初稿为 version 1；每次自动改写、人工改写、人工编辑追加新版本，不原地覆盖旧版本。
- [ ] **GEN-05 版本来源（P1）**：版本明确标记 generation、auto rewrite、human rewrite、human edit 等 origin，并保留 change note/请求关联。
- [ ] **GEN-06 受控并发（P1）**：并发不超过 `MODEL_CONCURRENCY`；单槽失败不影响其他槽位提交。
- [ ] **GEN-07 运行统计（P0）**：requested/generated/failed/pending 与数据库 item/槽位一致，重试后仍守恒。
- [ ] **GEN-08 模型调用日志（P1）**：记录 operation、adapter/model、duration、status、token counts 和安全错误码；不默认保存完整 Prompt 或供应商原始 body。

## 7. 人工审核与强制通过

- [ ] **REVIEW-01 人工最终判断（P0）**：人工审核阶段 AI 仅按指令改写；正常通过、强制通过、未通过由用户明确操作。
- [ ] **REVIEW-02 直接编辑（P0）**：标题、正文、标签可编辑；保存创建新版本、运行确定性 hard 检查并留在人审状态。
- [ ] **REVIEW-03 选区准确性（P0）**：请求包含 field、selection_start/end、selected_text、instruction、expected_version；后端校验切片一致。
- [ ] **REVIEW-04 仅替换片段（P0）**：`rewrite_selection` 只返回替换片段，不能借机替换整篇；用户能预览/决定是否采用。
- [ ] **REVIEW-05 并发冲突保护（P0）**：409 时前端保留本地编辑和人工指令，不静默重载覆盖。
- [ ] **REVIEW-06 QC 证据定位（P1）**：定位按钮聚焦字段并选中真实 evidence；不能精确定位时明确说明，不伪造选区。
- [ ] **REVIEW-07 普通通过门槛（P0）**：未解决 hard finding 存在时后端拒绝 human pass，不能仅靠前端禁用实现。
- [ ] **REVIEW-08 强制通过预填（P0）**：弹窗自动带入全部未解决问题，用户可补充放行理由。
- [ ] **REVIEW-09 强制通过非空（P0）**：前端和后端均拒绝空白/纯空格遗留问题；完成后显示“强制通过 · 有遗留问题”。
- [ ] **REVIEW-10 强制通过审计（P0）**：review event 保存 item、版本、事件、理由、完整遗留问题和时间；不可由后续编辑覆盖。
- [ ] **REVIEW-11 操作顺序（P1）**：底部固定为保存修改、未通过、强制通过、正常通过；视觉层级符合规范。
- [ ] **REVIEW-12 召回与再输出（P0）**：已输出 item 召回、编辑并再次完成后不会篡改旧 Sheet；下一次输出创建新 export run。

## 8. 飞书子 Sheet、幂等与输出边界

- [ ] **EXPORT-01 仅作为输出（P0）**：飞书不作为过程数据源，不反向读取或管理本地人工修改；SQLite 保持权威。
- [ ] **EXPORT-02 项目表格边界（P0）**：使用 `.env` 的 `FEISHU_SPREADSHEET_TOKEN`；每个 export run 在同一电子表格中新建一个子 Sheet。
- [ ] **EXPORT-03 输出范围（P0）**：只选择 `workflow_status=completed`；待 AI QC、AI QC 中、AI 修改中、待人工审核和 rejected 均不进入正式行。
- [ ] **EXPORT-04 三种完成方式（P0）**：正确映射 AI 自动通过、人工通过、强制通过；强制通过行包含非空遗留问题。
- [ ] **EXPORT-05 固定列（P0）**：顺序严格为序号、item_id、文案类型、标题、正文、话题标签、完成方式、遗留问题、修改说明。
- [ ] **EXPORT-06 确定行序（P0）**：同一 export run 的行集合和顺序稳定；重试不会改变序号或重复 item。
- [ ] **EXPORT-07 export ID 幂等（P0）**：`export_run_id` 为共同幂等键；同一成功请求重复提交返回原结果，不建新 Sheet。
- [ ] **EXPORT-08 Sheet 创建幂等（P0）**：一旦本地有 `sheet_id`，任何失败重试跳过 create；同一 export run 永远只有一个子 Sheet。
- [ ] **EXPORT-09 写入幂等（P0）**：使用固定表头和目标范围覆盖，不在末尾盲目追加；部分写入后重试不会产生重复行。
- [ ] **EXPORT-10 失败隔离（P0）**：飞书失败只更新 export run 错误，不重新生成、不重新 QC、不修改 item 完成状态。
- [ ] **EXPORT-11 新版本新 Sheet（P0）**：成功输出后召回/编辑/重新完成，必须创建新的 export run 和子 Sheet，不覆盖历史。
- [ ] **EXPORT-12 安全错误（P0）**：鉴权、权限、限流、建 Sheet、写行错误映射为固定错误码；不暴露供应商 body 或凭证。
- [ ] **EXPORT-13 Fake 明示（P1）**：Fake Exporter 产生稳定 fake sheet ID，UI 明确显示“模拟输出”，不得伪装真实飞书成功。
- [ ] **EXPORT-14 输出历史（P1）**：显示 generation run、export run、sheet title/ID 的安全表示、状态、行数、时间和安全错误，且可追溯。

## 9. Secret、文件与日志安全

- [ ] **SEC-01 `.env` 不入库（P0）**：Git 历史、当前索引和工作树不跟踪 `.env`；只提交无真实值的 `.env.example`。
- [ ] **SEC-02 数据文件不入库（P0）**：SQLite、WAL/SHM、上传文件、临时文件、Playwright trace/截图/视频和运行日志被正确忽略。
- [ ] **SEC-03 后端独占秘密（P0）**：API Key、App Secret、Spreadsheet Token 只由后端环境读取；前端无输入框、无 localStorage/sessionStorage 保存。
- [ ] **SEC-04 连接状态最小化（P0）**：`/api/system/connections` 只返回 configured、adapter 和允许的非敏感 model 名；不得返回 ID、token、secret、Base URL 中的凭证。
- [ ] **SEC-05 前端 bundle 扫描（P0）**：构建产物搜索不到真实秘密、`.env` 值、Authorization 或 Spreadsheet Token。
- [ ] **SEC-06 日志脱敏（P0）**：Authorization、Cookie、API key、app secret、token 和供应商原始错误 body 不进入日志、model_call_logs 或前端错误详情。
- [ ] **SEC-07 启动错误脱敏（P0）**：配置缺失只列变量名，不打印变量值；异常堆栈不返回前端。
- [ ] **SEC-08 上传路径安全（P0）**：验证路径穿越、绝对路径、保留设备名、重复文件名和恶意扩展；服务端不信任客户端 MIME/文件名。
- [ ] **SEC-09 Prompt/原帖存储边界（P1）**：默认不在调用日志保存完整 Prompt；业务需要保存的 Brief/参考原帖只存在受控上传目录和 SQLite 关联记录。
- [ ] **SEC-10 API 客户端同源（P0）**：前端 API client 拒绝绝对 URL，防止将项目内容或秘密发送到非预期域名。
- [ ] **SEC-11 错误响应（P0）**：所有 API 错误使用安全统一格式，不包含 SQL、文件绝对路径、堆栈或供应商原始响应。
- [ ] **SEC-12 依赖与构建（P1）**：锁文件存在；依赖安装可复现；无已知会阻断本地交付的高危依赖问题。

## 10. SQLite 模式、约束与事务

> 注意：实施计划正文列出了 14 张领域表，但 Task 3 文案写成“12 张表”。终审以明确列出的领域实体为准，不允许用数量口径差异省略表。

### 10.1 表与迁移

- [ ] **DB-01 表完整（P0）**：存在并实际使用 `projects`、`brief_sources`、`copy_types`、`reference_examples`、`qc_rules`、`generation_runs`、`copy_items`、`copy_item_versions`、`qc_runs`、`qc_findings`、`rewrite_requests`、`review_events`、`export_runs`、`model_call_logs`，以及迁移记录表。
- [ ] **DB-02 迁移幂等（P0）**：空库迁移成功；重复迁移不报错、不重建/丢失数据；schema version 可追溯。
- [ ] **DB-03 外键启用（P0）**：每个连接执行 `PRAGMA foreign_keys=ON`；孤儿 project/type/item/version/QC/export 记录无法写入。
- [ ] **DB-04 WAL 与等待（P1）**：`journal_mode=WAL`、`busy_timeout=5000` 生效；多请求下不会立即产生可避免的 database locked。
- [ ] **DB-05 显式事务（P0）**：关键写路径使用显式事务，异常 rollback；无半条 generation/QC/review/export 记录。

### 10.2 唯一、状态与业务约束

- [ ] **DB-06 UUID（P1）**：所有领域 ID 使用合法 UUID 字符串；Fake sheet ID 等外部标识不冒充领域 UUID。
- [ ] **DB-07 版本唯一（P0）**：`copy_item_versions(item_id, version)` 唯一，递增版本在并发下不冲突。
- [ ] **DB-08 槽位唯一（P0）**：`copy_items(run_id, copy_type_id, ordinal)` 唯一。
- [ ] **DB-09 规则归属（P0）**：项目规则 `copy_type_id IS NULL`，类型规则必须非空且属于同一 project。
- [ ] **DB-10 类型输入模式（P0）**：input modes 只允许 reference_examples/description_requirements 的合法组合；参考模式强制 1–5 条完整案例和非空已确认画像。
- [ ] **DB-11 完成约束（P0）**：状态/completion reason 组合在数据库或事务仓储层被强制校验。
- [ ] **DB-12 强制通过约束（P0）**：服务和事务保证 forced_pass 同时存在非空 legacy issues review event；无法产生孤立 forced_pass。
- [ ] **DB-13 输出幂等（P0）**：export run ID 唯一；已有 sheet_id 的失败重试无法创建第二条/第二 Sheet 映射。
- [ ] **DB-14 删除保护（P0）**：有生成记录的类型无法删除或导致历史断链；项目归档不删除审计数据。
- [ ] **DB-15 预期旧状态（P0）**：仓储状态更新带 expected old status/version，受影响行数异常时回滚并返回冲突。

### 10.3 JSON 与审计数据

- [ ] **DB-16 JSON 严格校验（P0）**：所有 JSON TEXT 字段写入前和读取后经禁止额外字段的 Pydantic schema 校验；损坏数据不会静默当空值处理。
- [ ] **DB-17 原始供应商响应隔离（P0）**：CLIPROXY/飞书原始 JSON 不直接写入业务 JSON 字段。
- [ ] **DB-18 配置快照（P0）**：run snapshot 包含可复现所需的项目事实、类型、有效规则、参考画像和原帖，但不包含 secret。
- [ ] **DB-19 审计追加不覆盖（P0）**：item versions、QC runs/findings、rewrite requests、review events、export runs 采用追加记录；更新当前状态不抹除历史。
- [ ] **DB-20 备份恢复（P1）**：README 给出安全备份 SQLite/WAL 的方法；实测恢复后项目、版本和审计链完整。

## 11. REST、模型与前端 API 合同

### 11.1 REST 基础合同

- [ ] **API-01 路由完整（P0）**：实施计划 REST 概览中的 health、connections、projects、brief parse、copy types、references、classification、rules、generation runs、board、items、QC retry、selection rewrite、review、exports 路由均存在。
- [ ] **API-02 统一错误（P0）**：非 2xx 返回 `{ "error": { "code", "message", "details" } }`；前端对无效 JSON 映射 `API_RESPONSE_INVALID`。
- [ ] **API-03 HTTP 语义（P0）**：上传过大 413、不支持格式 415、模型未配置 503、版本冲突 409、非法转换使用稳定业务错误码。
- [ ] **API-04 只读字段保护（P0）**：PATCH 忽略或拒绝客户端伪造的 ID、project_id、created_at、状态、计数和审计字段。
- [ ] **API-05 项目归属检查（P0）**：嵌套路由和资源 ID 均验证同一 project/type/run 归属，不能跨项目引用规则、类型、item 或 reference。
- [ ] **API-06 分页/上限（P1）**：列表和批量请求遵守计划数量限制，恶意大数组不会绕过 100 条生成上限或 20 个附件上限。
- [ ] **API-07 响应最小化（P1）**：看板卡片不返回完整正文；详情端点才返回编辑所需内容和 QC 历史。

### 11.2 模型适配器合同

- [ ] **MODEL-01 六个方法（P0）**：parse_brief、analyze_reference_examples、generate_copy、run_semantic_qc、rewrite_copy、rewrite_selection 均由 Protocol、Fake、CLIPROXY 实现。
- [ ] **MODEL-02 严格 schema（P0）**：所有模型返回先解析为禁止额外字段的 Pydantic 类型；非法/空输出不覆盖现有数据。
- [ ] **MODEL-03 CLIPROXY 请求（P0）**：使用 Bearer、`/v1/responses` 兼容请求，包含 model/instructions/input/max_output_tokens 和可选 reasoning.effort。
- [ ] **MODEL-04 模型选择（P0）**：semantic QC 使用 QC model，其余五项使用 generation model；环境缺失时安全启动失败或明确未配置。
- [ ] **MODEL-05 响应兼容（P0）**：支持顶层 `output_text` 和 `output[].content[].text`，均进入同一内部 schema。
- [ ] **MODEL-06 错误映射（P0）**：401、429、timeout、非 JSON、空输出、schema invalid、unavailable 映射为约定错误；Retry-After 生效。
- [ ] **MODEL-07 Fake 确定性（P1）**：相同输入得到相同输出；`[FAIL_QC]`、`[MODEL_ERROR]`、`[LOW_CONFIDENCE]` 可稳定驱动测试且不联网。
- [ ] **MODEL-08 幂等键（P1）**：生成/改写调用带稳定 idempotency key，或由本地服务在重试前去重；不得因轮询重复计费。

### 11.3 前端合同

- [ ] **API-08 TypeScript 合同一致（P0）**：TS union/interface 与 Pydantic 响应一致；未知状态不会被错误归入某列。
- [ ] **API-09 请求取消/竞态（P1）**：页面切换、重复保存和轮询不会让旧响应覆盖新数据。
- [ ] **API-10 轮询纪律（P0）**：页面可见且有运行项时每 2 秒轮询；隐藏暂停；未完成请求不叠加；失败保留旧数据。
- [ ] **API-11 筛选稳定（P1）**：run/type/completion reason 筛选写入 URL query，刷新后保持。
- [ ] **API-12 输出重试合同（P0）**：前端失败重试始终复用原 export ID；有 sheet_id 时不生成新 ID。

## 12. 前端五列、视觉、响应式与可访问性

### 12.1 应用骨架与设计 Token

- [ ] **UI-01 应用壳（P1）**：桌面外边距 16px、主壳 28px 圆角、72px 图标栏、48px 顶部悬浮导航。
- [ ] **UI-02 导航顺序（P0）**：项目、帖子类型、QC 要求、文案看板、飞书输出；UI 统一用“帖子类型”。
- [ ] **UI-03 单一 Token（P1）**：颜色、间距、圆角、阴影、字号和状态映射集中维护；JSX 无散落色值。
- [ ] **UI-04 色彩约束（P1）**：使用规范 OKLCH token；不使用纯白 `#fff`/纯黑 `#000`、渐变文字、玻璃拟态或彩色侧边条。
- [ ] **UI-05 视觉层级（P2）**：最多两层视觉海拔，卡片不出现粗边框、强阴影和高饱和背景叠加。
- [ ] **UI-06 控件状态（P1）**：按钮具备 default、hover、focus-visible、active、disabled、loading。

### 12.2 固定五列看板

- [ ] **BOARD-01 列数与顺序（P0）**：始终显示待 AI QC、AI QC 中、AI 修改中、待人工审核、已完成五列，空列也存在。
- [ ] **BOARD-02 无额外流程列（P0）**：没有“一轮修改/二轮修改”列；修改次数为卡片元数据。
- [ ] **BOARD-03 不可拖拽（P0）**：P0 不允许跨列拖动，状态只由合法业务动作改变。
- [ ] **BOARD-04 统计守恒（P0）**：总文案等于五列 count 之和；AI 处理中等于 AI QC 中 + AI 修改中。
- [ ] **BOARD-05 状态集中映射（P0）**：文案、背景 token、图标、动作集中在 status presentation；颜色与实际状态无错配。
- [ ] **BOARD-06 卡片信息（P1）**：显示 item ID、用户类型、标题/进度、问题、相似项/相似度、修改次数和更新时间。
- [ ] **BOARD-07 完成方式（P0）**：已完成卡片区分 AI 自动通过、人工通过、强制通过且有遗留问题。
- [ ] **BOARD-08 失败保留（P0）**：API 失败不清空卡片；显示安全错误并提供合法的单条重试。

### 12.3 人工审核 UI

- [ ] **UI-07 桌面布局（P1）**：审核面板约 68vw、最低 960px；左 64% 编辑、右 36% QC；小屏不强制最低宽度。
- [ ] **UI-08 选区入口（P0）**：非空选区显示“让 AI 修改”，同时支持右键和键盘可达入口。
- [ ] **UI-09 可控编辑（P0）**：标题/正文/标签编辑状态由前端受控；保存、409、API 失败均不丢输入。
- [ ] **UI-10 强制通过界面（P0）**：自动带入未解决问题；纯空格不可提交；补充理由明确；完成卡片显示遗留风险。

### 12.4 响应式

- [ ] **RESP-01 ≥1440px（P1）**：五列完整展示，列最小宽 240px、间距 16px。
- [ ] **RESP-02 1024–1439px（P1）**：保持列宽并横向滚动，不压缩任务卡。
- [ ] **RESP-03 768–1023px（P1）**：隐藏图标栏，顶部导航改横向滚动标签。
- [ ] **RESP-04 ≤767px（P0）**：看板变单列状态列表，用分段控件切换；审核为全屏纵向布局。
- [ ] **RESP-05 字号与内容（P1）**：不使用 clamp/流式字号；长内容有完整查看入口，不因断点丢失操作。

### 12.5 可访问性与边界状态

- [ ] **A11Y-01 对比度（P0）**：正文至少 4.5:1；粉彩背景仍使用主文字色，实测关键组合。
- [ ] **A11Y-02 非颜色表达（P0）**：状态同时有文字或图标，不只靠颜色。
- [ ] **A11Y-03 图标名称（P0）**：所有图标按钮有准确 `aria-label`。
- [ ] **A11Y-04 键盘路径（P0）**：无需鼠标可进入导航、任务卡、审核、QC 定位、编辑、选区 AI 修改、通过/强制通过和输出操作。
- [ ] **A11Y-05 焦点管理（P0）**：对话框/审核面板有焦点圈定，Escape 关闭，关闭后焦点回触发按钮；`:focus-visible` 清晰。
- [ ] **A11Y-06 表单语义（P0）**：label、错误、帮助文本与控件关联；强制通过错误可被读屏宣布。
- [ ] **A11Y-07 加载与空状态（P1）**：使用内容骨架；空状态说明下一步；不是无说明 spinner/空白页。
- [ ] **A11Y-08 错误恢复（P0）**：错误提示可聚焦/可读，保留数据和编辑文本，并给出可执行重试。
- [ ] **A11Y-09 减少动效（P0）**：`prefers-reduced-motion` 下关闭位移；不使用弹跳或 width/height/left/top 动画。
- [ ] **A11Y-10 动效时长（P2）**：普通交互 150–220ms，审核面板约 220ms，仅 transform/opacity。

## 13. 自动测试与端到端验收

### 13.1 后端单元/集成/合同测试

- [ ] **TEST-01 状态转换测试（P0）**：覆盖全部合法分支、非法事件、强制通过空遗留问题和 recall。
- [ ] **TEST-02 数据库测试（P0）**：覆盖迁移幂等、外键、唯一约束、状态不变量、事务 rollback、删除保护和并发版本冲突。
- [ ] **TEST-03 Brief 测试（P0）**：覆盖 txt/md/docx、BOM、DOCX 表格、空文件、超限、PDF 拒绝、路径安全和解析失败记录。
- [ ] **TEST-04 模型合同测试（P0）**：Fake 与 CLIPROXY 六方法均通过相同 schema；MockTransport 覆盖两类响应形状和全部错误映射。
- [ ] **TEST-05 规则测试（P0）**：项目 hard 不可覆盖、类型 soft 覆盖项目 soft、hard 冲突阻断、must/avoid 派生规则。
- [ ] **TEST-06 参考隔离测试（P0）**：原帖完整保存并进 Prompt、画像进 Prompt、来源事实隔离、禁抄分区、参考相似度命中。
- [ ] **TEST-07 生成恢复测试（P0）**：稳定 item ID、槽位唯一、单槽重试、重启恢复、成功项不重复调用。
- [ ] **TEST-08 QC 工作流测试（P0）**：AI 直通、自动改写复检、hard/低置信度/相似度转人工、重试耗尽、模型异常保留内容。
- [ ] **TEST-09 人审测试（P0）**：直接编辑、选区校验、409、普通通过门槛、强制通过预填/非空、reject、recall。
- [ ] **TEST-10 看板测试（P0）**：固定五列、空列、统计守恒、三种完成方式、单条重试条件。
- [ ] **TEST-11 输出合同测试（P0）**：只输出 completed、固定列序、同 export ID 不重复建 Sheet、固定范围覆盖、错误不触发生成/QC。

### 13.2 前端测试

- [ ] **TEST-12 API client（P0）**：拒绝绝对 URL、统一错误、无效 JSON、409 保留输入。
- [ ] **TEST-13 项目与类型 UI（P0）**：四区编辑保存、无预设类型、类型 Brief、1–5 参考案例、画像确认、默认 QC 和生成阻断摘要。
- [ ] **TEST-14 看板 UI（P0）**：五列/统计/轮询/筛选/失败保留/三种完成方式。
- [ ] **TEST-15 审核 UI（P0）**：操作顺序、选区三种入口、定位、AI 改写后留人审、普通/强制通过约束。
- [ ] **TEST-16 输出 UI（P0）**：无 secret 输入、completed 预览、排除数量、原 export ID 重试、Fake 标识和历史。
- [ ] **TEST-17 可访问性测试（P0）**：键盘、焦点圈定/恢复、aria-label、表单错误、减少动效和移动端关键路径。

### 13.3 E2E 场景

- [ ] **E2E-01 AI 直通（P0）**：建项目 → Brief 拆解保存 → 建类型 → 规则 → 生成 → AI QC → `completed/ai_pass`。
- [ ] **E2E-02 参考帖类型（P0）**：1–5 原帖 → 画像 → 事实隔离 → must/avoid 默认 QC → Prompt 同含原帖/画像 → 防照搬通过。
- [ ] **E2E-03 异常人工审核（P0）**：自动修改耗尽 → 人审 → 直接编辑仍人审 → 选区 AI 改写仍人审 → 普通通过。
- [ ] **E2E-04 强制通过（P0）**：空遗留问题阻止 → 自动带入 finding → 补充理由 → forced_pass → 输出含遗留问题。
- [ ] **E2E-05 输出幂等（P0）**：首次建一个 Fake Sheet；同 export ID 重试不增 Sheet；未完成/未通过不进输出。
- [ ] **E2E-06 重启恢复（P0）**：运行中重启服务，完成后无重复 item、版本或模型调用。
- [ ] **E2E-07 移动端键盘替代（P0）**：窄屏关键审核/输出流程可完成；桌面仅键盘可完成定向改写和审核。

### 13.4 全量命令

- [ ] **TEST-18 Pytest**：`python -m pytest backend/tests -q`，退出码 0。
- [ ] **TEST-19 Ruff**：`python -m ruff check backend`，退出码 0。
- [ ] **TEST-20 前端单测**：`npm --prefix frontend test -- --run`，退出码 0。
- [ ] **TEST-21 TypeScript**：`npm --prefix frontend run typecheck`，退出码 0。
- [ ] **TEST-22 生产构建**：`npm --prefix frontend run build`，退出码 0。
- [ ] **TEST-23 Playwright**：`npm --prefix frontend exec playwright test -- --config ../e2e/playwright.config.ts`，退出码 0；失败 trace 不提交 Git。

## 14. CLIPROXY 与飞书实网验证

> 实网验证必须使用专用测试项目、最少数据和受控成本。缺凭证或权限时标记 BLOCKED，并明确“仅 Fake/合同测试已验证”；不得猜测 URL、模型名、错误码或权限。

### 14.1 验证前门槛

- [ ] **LIVE-01 CLIPROXY 配置齐全（P0/BLOCKABLE）**：Base URL、API Key、generation/QC model、endpoint/样例、并发/频率/timeout/token 限制已由用户或供应商提供。
- [ ] **LIVE-02 飞书配置齐全（P0/BLOCKABLE）**：App ID、App Secret、Spreadsheet Token、创建子 Sheet/写单元格权限、限流/错误码资料齐全。
- [ ] **LIVE-03 测试隔离（P0）**：使用明确的测试项目和测试电子表格；记录预期创建的子 Sheet 数，不触碰生产内容。
- [ ] **LIVE-04 Secret 处理（P0）**：凭证仅写本地 `.env`，终审记录只写变量是否配置，不复制实际值。

### 14.2 CLIPROXY smoke test

- [ ] **LIVE-05 健康请求（P0/BLOCKABLE）**：实际 `/v1/responses` 请求成功，鉴权、endpoint 和模型名与合同一致。
- [ ] **LIVE-06 Brief 解析（P0/BLOCKABLE）**：真实 parse 返回严格四区 schema、依据和置信度，不补写缺失事实。
- [ ] **LIVE-07 参考分析（P0/BLOCKABLE）**：真实 analyze 生成可编辑画像、来源事实和避免照搬表达，来源事实不写项目。
- [ ] **LIVE-08 生成请求（P0/BLOCKABLE）**：用最小测试 Brief 证明真实 Prompt 携带项目事实、原帖、画像和禁用分区；返回标题/正文/标签 schema。
- [ ] **LIVE-09 语义 QC（P0/BLOCKABLE）**：真实 QC 返回 finding/置信度，不直接修改文案或作强制通过决定。
- [ ] **LIVE-10 两类改写（P0/BLOCKABLE）**：整稿改写只修复指定问题；选区改写只返回替换片段；均不新增事实。
- [ ] **LIVE-11 错误与限流（P1/BLOCKABLE）**：在不泄露凭证、不恶意触发供应商限制的前提下，验证可安全观察的 auth/timeout/rate-limit 映射或以供应商样例 + MockTransport 补证。
- [ ] **LIVE-12 业务无差异（P0/BLOCKABLE）**：切换真实适配器后，状态、数据库和前端 response schema 与 Fake 路径一致。

### 14.3 飞书 smoke test

- [ ] **LIVE-13 连接与权限（P0/BLOCKABLE）**：真实凭证可访问指定 Spreadsheet，并具备创建子 Sheet 和写目标范围权限。
- [ ] **LIVE-14 首次输出（P0/BLOCKABLE）**：一个真实 export run 恰好新建一个子 Sheet，固定表头和 completed 行正确。
- [ ] **LIVE-15 数据正确性（P0/BLOCKABLE）**：item_id、类型、标题、正文、标签、完成方式、遗留问题、修改说明与 SQLite 快照逐行一致。
- [ ] **LIVE-16 同 ID 重试幂等（P0/BLOCKABLE）**：重复提交同一成功 export ID 返回原结果，电子表格子 Sheet 数不增加。
- [ ] **LIVE-17 写入重试幂等（P0/BLOCKABLE）**：以安全、可控方式验证已有 sheet_id 的重试只覆盖固定范围，不重复行、不再建 Sheet。
- [ ] **LIVE-18 失败隔离（P0/BLOCKABLE）**：可安全模拟/观察权限或写入失败时，不触发生成/QC，item 与版本不变。
- [ ] **LIVE-19 新运行新 Sheet（P0/BLOCKABLE）**：召回、编辑、重新完成后创建新 export run 和第二个子 Sheet，旧 Sheet 不变。
- [ ] **LIVE-20 限流与错误展示（P1/BLOCKABLE）**：真实错误码映射为安全内部码，UI 可重试且不显示原始 secret/body。

## 15. 文档、运维与故障恢复

- [ ] **DOC-01 README 完整（P0）**：包含 Windows 安装、`.env` 复制、Fake 演示、数据库备份、支持格式、状态机、测试命令、实网边界和故障恢复。
- [ ] **DOC-02 `.env.example` 一致（P0）**：字段与外部接入契约/配置类一致，无真实值；默认 Fake/未配置飞书可启动。
- [ ] **DOC-03 外部合同一致（P0）**：六个模型方法、错误映射、超时、幂等、飞书 create/write、固定列和重试行为与代码一致。
- [ ] **DOC-04 启动脚本（P0）**：`dev.ps1`、`build.ps1`、`start.ps1` 在干净 Windows 环境可运行，目录/`.env` 缺失给出安全可操作错误。
- [ ] **DOC-05 故障恢复（P0）**：文档覆盖模型失败、QC 中断、重启恢复、飞书部分失败、SQLite 备份恢复和单条重试。
- [ ] **DOC-06 能力声明诚实（P0）**：若实网项 BLOCKED，README/交付说明明确“Fake + 合同测试通过，真实 CLIPROXY/飞书未验证”。

## 16. 终审缺陷汇总

| 缺陷 ID | 优先级 | 检查项 | 现象与复现 | 影响 | 修复状态 | 复验结果 |
|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |

## 17. 终审证据索引

| 证据 ID | 类型 | 对应检查项 | 路径/命令/安全摘要 | 日期 |
|---|---|---|---|---|
|  |  |  |  |  |

## 18. 终审签署

```text
终审结论：可交付 / 有条件可交付 / 不可交付
P0：PASS __ / FAIL __ / BLOCKED __
P1：PASS __ / FAIL __ / BLOCKED __
P2：PASS __ / FAIL __ / BLOCKED __
实网状态：CLIPROXY ______；飞书 ______
未解决风险：
终审人：
终审日期：
```
