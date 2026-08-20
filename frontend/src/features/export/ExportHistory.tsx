import type { ExportRun } from "../../api/contracts";
import { EmptyState } from "../../components/EmptyState";
import { Icon } from "../../components/Icon";

const statusLabels = { pending: "等待输出", running: "输出中", succeeded: "输出成功", failed: "输出失败" };

export function ExportHistory({ items, onRetry }: { items: ExportRun[]; onRetry: (item: ExportRun) => void }) {
  return <section><div className="section-heading"><div><h2>输出历史</h2><p className="page-description">失败重试沿用原 export ID；已有 Sheet 时继续写入原子 Sheet。</p></div></div>{items.length === 0 ? <div className="panel"><EmptyState icon="export" title="还没有输出记录" description="完成文案后创建一次飞书输出，历史会保留在这里。" /></div> : <div className="export-history">{items.map((item) => <article className="surface-card export-row" key={item.id}><div><span className={`status-chip ${item.status === "succeeded" ? "success" : item.status === "failed" ? "danger" : "warning"}`}>{statusLabels[item.status]}</span>{item.adapter === "fake" && <span className="source-chip">模拟输出</span>}</div><div><h3>{item.sheet_title}</h3><p className="meta">{item.id} · {new Date(item.created_at).toLocaleString("zh-CN")}</p>{item.sheet_id && <small>Sheet ID：{item.sheet_id}</small>}</div><strong className="export-count">{item.row_count}<small> 行</small></strong>{item.safe_error && <p className="safe-error">{item.safe_error}</p>}{item.status === "failed" && <button className="button button-secondary" onClick={() => onRetry(item)}><Icon name="retry" />重试原输出</button>}</article>)}</div>}</section>;
}
