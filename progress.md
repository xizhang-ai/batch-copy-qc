# 规划进度日志

## 2026-08-24

- 用户提出将项目改为对话驱动的简化入口，并认可默认先生成 3 篇预览。
- 已检查现有生成 run、冻结快照、item slot、worker、前端三组看板和 API 结构。
- 已创建实施计划 `docs/superpowers/plans/2026-08-24-conversational-preview-flow.md`；本轮仅写计划，未开始对话能力、预览批次或新页面的编码。

## 2026-08-21

- 用户授权开始完整计划，但要求停在长任务编码前的最后一步。
- 已创建持久化规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 已明确本阶段只修改 Markdown 文档，不安装依赖、不创建应用代码、不启动服务。
- 已读取 `README.md`、短策划和技术选型。
- 已视觉核对看板与人工审核参考图，并把可复用布局及旧口径冲突记录到 `findings.md`。
- 已同步短策划与技术选型中的旧流程口径。
- 已创建 `docs/frontend-visual-spec-v0.1.md`，把确认的视觉规范和最新状态机固化为实现基线。
- 已创建完整实施计划 `docs/superpowers/plans/2026-08-21-batch-copy-qc-mvp.md`，拆分为 22 个可独立测试和提交的任务。
- 已创建 `docs/external-integration-contract.md`，固定 `.env`、模型六方法、飞书幂等输出、错误分类和合同测试边界。
- 用户在计划收口前新增“从一篇爆款文案参考建立帖子类型”；已暂停最终自检，开始把该能力补入全链路计划。
- 用户提供了“参考案例 / 描述要求 + 一定要有 / 一定不要有”的参考逻辑；决定采用可组合依据并保持本产品视觉，不照搬页面。
- 用户确认：保留 AI 风格拆解；完整原帖也要保存并进入生成 Prompt；每类型最多 5 篇；未单独填写类型 QC 时，明确约束自动成为默认类型 QC。
- 已把新逻辑同步到短策划、视觉规范、外部接入契约和 22 项实施计划。
- 已完成最终扫描：目录中只有 9 个 Markdown 文件，没有应用源码或非 Markdown 产物；未发现 TODO/TBD、省略实现、旧 1–3 篇限制或旧五方法口径。
- 规划阶段已完成。下一次长任务从完整计划 Task 1 初始化独立 Git 仓库开始。
- 用户补充模型 API 使用 CLIPROXY；已重新打开规划文档，仅更新供应商适配边界，不启动编码。
- 已把 CLIPROXY 的 `.env` 字段、Responses 兼容请求、HTTP 错误映射、MockTransport 合同测试和实网验证门槛写入完整计划。
- 用户已授权开始长任务，并明确允许子智能体或工作树协作，要求设置独立审查官。
- 已验证 CLIPROXY 生成/QC 模型真实请求、飞书应用鉴权、Wiki→Sheet 解析及 Sheets 读取接口均通过；测试过程未写入飞书。
- 长任务分工：后端、前端、审查官三条并行线；主智能体负责仓库初始化、接口集成、E2E、实网输出与最终修复。
- 已初始化独立 Git；首次提交因本机未配置 Git author 被拒绝，决定只设置仓库级 Codex 身份后重试。
- 已完成规划基线提交 `f00c88d`。发现系统 Python 为 3.14，已通知后端线切换到 bundled Python 3.12.13，并要求排除生成的 pyc。
- 审查官已建立 19 章终审检查表并发现“14 张领域表/Task 3 写 12 张”的文案差异；实现统一按 14 张领域表验收。
- 为减少后端串行瓶颈，新增外部适配器实现线，独占 `backend/app/model/**`、`backend/app/export/**` 与合同测试；核心后端明确避开这些路径。
- 后端、前端和外部适配器三条实现线完成；独立审查官经过三轮复核，Responses 协议、飞书幂等、不可变输出快照、强制通过枚举、token 刷新和升级迁移等 P0 全部放行。
- 主集成补齐项目品牌/品类保存、类型 Brief 真实回填、动态批次摘要、favicon、FastAPI 静态托管与 SPA fallback。
- 创建 `examples/` 三份虚构演示材料、5 条 Chromium E2E、Windows `dev/build/start` 脚本和完整 README。
- 使用真实 `.env` 完成 CLIPROXY 最小 Responses 解析 smoke test；返回严格 Pydantic 结构。内容分类质量仍按计划属于 P1。
- 使用真实飞书配置完成 tenant 鉴权、Wiki→Sheet 解析及工作表列表读取；未创建、未修改任何真实 Sheet。
- 建立项目内 `.venv` 并验证 `scripts/build.ps1`；验证 `scripts/start.ps1` 单 worker 静态服务：根页面、SPA 路由、favicon、health 均 200，未知 API 为 JSON 404。
- 最终回归：后端 74 passed、Ruff 全绿；前端 9 files/11 tests、typecheck、build 全绿；Chromium E2E 5 passed。
- 安全扫描检查 `.env` 中 3 个非空秘密值未出现在源码、文档或前端 bundle；`.env`、`.venv`、data、output、trace、dist 均已被 Git 忽略。
- 独立审查官全仓终审发现真实前端默认 Mock、类型 Brief 语义映射、实际规则合并、重启恢复、相似度 hard finding 绕过、API 错误合同、跨项目规则归属、类型文件分类和 Mock-only E2E 等停发问题；已撤回完成状态并进入并行修复。
- `dev.ps1` 首版 Ctrl+C 会遗留后台子服务；已改为 Uvicorn 前台、Vite 后台并按精确进程树清理，复测停止后无 8000/5173 LISTENING。
- 首轮终审停发项全部修复：生产前端默认真实 API、项目/类型 Brief 语义拆解与恢复、类型文件真实分类、规则合并、重启恢复、Hard finding、统一错误合同及真实栈 E2E。
- 第二轮终审补齐项目/类型 Brief QC 物化去重、类型冲突逐条审阅与持久化、同类多 Hard 规则、结构化语义 QC 身份、人工编辑后完整复检、强制通过空白校验与类型文件解绑。
- 第三轮终审补齐强制通过双字段真实契约、Hard/Soft 冲突边界、保存/选区改写完整 item 响应与前端 partial-response 防御，并修复 SQLite 单连接并发风险。
- SQLite 改为每个 HTTP 请求独立连接、后台 worker 专用连接；12 个并发 worker 共 96 次混合读写测试通过，连接释放已有自动回归。
- 最终冻结回归：后端 100 passed、Ruff 通过；前端 9 files/15 tests、TypeScript、生产构建通过；Mock Playwright 5/5、真实 FastAPI + SQLite + Fake Adapter E2E 1/1。
- 真实 E2E 覆盖多行 Brief、类型审阅持久化、生成与 AI QC、人工保存后正常通过、再次召回、双字段强制通过及相同 export run 幂等重试；结束后 8000/4177/5173 均无监听。
- 生产 bundle 无 Mock fixture；`.env` 未跟踪，真实秘密值扫描无命中；`git diff --cached --check` 与独立审查官 cached-only 复核通过。
- 独立审查官最终结论：PASS，可放行当前冻结版本，P0/P1/P2 均为 0。
- 外部实网边界保持不变：CLIPROXY 仅完成 Responses parse smoke test；飞书只完成鉴权、Wiki 解析与只读查询，未获授权的真实写入未执行。
