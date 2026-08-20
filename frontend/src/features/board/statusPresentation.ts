import type { IconName } from "../../components/Icon";
import type { CompletionReason, WorkflowStatus } from "../../api/contracts";

export interface StatusPresentation { label: string; className: string; icon: IconName; description: string }

export const boardStatuses: WorkflowStatus[] = ["pending_ai_qc", "ai_qc_running", "ai_rewrite_running", "human_review", "completed"];

export const statusPresentation: Record<WorkflowStatus, StatusPresentation> = {
  pending_ai_qc: { label: "待 AI QC", className: "status-pending", icon: "file", description: "等待审查官领取" },
  ai_qc_running: { label: "AI QC 中", className: "status-qc", icon: "qc", description: "正在核对事实与规则" },
  ai_rewrite_running: { label: "AI 修改中", className: "status-rewrite", icon: "spark", description: "修改完成后重新 QC" },
  human_review: { label: "待人工审核", className: "status-human", icon: "warning", description: "异常项或主动召回" },
  completed: { label: "已完成", className: "status-completed", icon: "check", description: "只输出此列内容" },
};

export const completionPresentation: Record<CompletionReason, { label: string; className: string }> = {
  ai_pass: { label: "AI 自动通过", className: "success" },
  human_pass: { label: "人工通过", className: "success" },
  forced_pass: { label: "强制通过 · 有遗留问题", className: "warning" },
};
