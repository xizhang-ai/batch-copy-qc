import type { BoardData } from "../../api/contracts";

export function BoardStats({ board }: { board: BoardData }) {
  const total = board.items.length;
  const processing = board.items.filter((item) => item.workflow_status === "ai_qc_running" || item.workflow_status === "ai_rewrite_running").length;
  const human = board.items.filter((item) => item.workflow_status === "human_review").length;
  const completed = board.items.filter((item) => item.workflow_status === "completed").length;
  return <section className="stats-grid" aria-label="看板统计">
    {[['总文案', total, '当前批次全部文案'], ['系统处理中', processing + board.items.filter((item) => item.workflow_status === "pending_ai_qc").length, '等待或正在自动处理'], ['需人工处理', human, '需要人工判断'], ['已完成', completed, '可进入飞书输出']].map(([label, value, note]) => <div className="surface-card stat-card" key={label}><span>{label}</span><strong>{value}</strong><small>{note}</small></div>)}
  </section>;
}
