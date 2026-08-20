# 小红书快消类种草批量文案与 QC 组件

本目录用于集中存放小红书快消类种草批量文案生成组件的全部相关内容，包括：

- 小红书标题、正文和话题标签生成逻辑与提示词模板
- Brief 上传与智能拆解，并分类为项目内容、文案需求和 QC 需求
- 拆解结果的可视化编辑，以及无预设的文案类型和文件分类
- 首版不内置模板，仅保留后续模板库扩展口
- 批量任务输入、输出与状态管理
- 项目/文案类型自动 QC，以及生成后的人工个例 QC
- 类型可单独上传 Brief，生成后的人工个例 QC 支持直接编辑或定向 AI 修改
- 同一项目写入同一飞书电子表格，每次输出新增一个子 Sheet
- 生成、QC、改写与 Brief/爆款参考分析统一通过 CLIPROXY Adapter 调用
- 配置、测试、样例数据和使用文档

后续新增的代码和资料均应保留在本目录内，避免与工作区中的其他项目混放。

## 当前阶段

短策划、技术选型、视觉规范和完整实施计划已经完成。目前停在长任务编码入口，尚未创建应用源码、安装依赖或启动服务。

权威文档：

- `docs/brief-proposal.md`：产品范围与流程。
- `docs/tech-stack-selection.md`：独立产品技术选型。
- `docs/frontend-visual-spec-v0.1.md`：前端视觉与交互基线。
- `docs/external-integration-contract.md`：模型与飞书 `.env` 接入边界。
- `docs/superpowers/plans/2026-08-21-batch-copy-qc-mvp.md`：长任务逐项实施计划。

## 目标目录

```text
batch-copy-qc/
├─ backend/      # FastAPI、SQLite、模型/QC/飞书适配边界
├─ frontend/     # React、TypeScript、Vite 与产品界面
├─ examples/     # 虚构项目与验收输入
├─ e2e/          # Playwright 端到端测试
├─ scripts/      # Windows 开发、构建、启动脚本
└─ docs/         # 产品、设计、技术与实施计划
```

具体目录会在相应功能开始实现时创建。
