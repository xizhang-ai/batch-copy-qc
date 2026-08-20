import type { BoardData } from "../../api/contracts";

export function BoardStats({ board }: { board: BoardData }) {
  const total = board.items.length;
  const processing = board.items.filter((item) => item.workflow_status === "ai_qc_running" || item.workflow_status === "ai_rewrite_running").length;
  const human = board.items.filter((item) => item.workflow_status === "human_review").length;
  const completed = board.items.filter((item) => item.workflow_status === "completed").length;
  return <section className="stats-grid" aria-label="看板统计">
    {[['总文案', total, '五列数量之和'], ['AI 处理中', processing, 'QC 中 + 修改中'], ['待人工审核', human, '需要人工判断'], ['已完成', completed, '可进入飞书输出']].map(([label, value, note]) => <div className="surface-card stat-card" key={label}><span>{label}</span><strong>{value}</strong><small>{note}</small></div>)}
  </section>;
}
