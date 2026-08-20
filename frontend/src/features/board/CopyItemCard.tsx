import type { CopyItem } from "../../api/contracts";
import { Icon } from "../../components/Icon";
import { completionPresentation, statusPresentation } from "./statusPresentation";

export function CopyItemCard({ item, onReview, onRetry }: { item: CopyItem; onReview: (trigger: HTMLButtonElement) => void; onRetry: () => void }) {
  const presentation = statusPresentation[item.workflow_status];
  return <article className="copy-item-card" tabIndex={0} aria-label={`${item.id} ${item.title}`}>
    <div className="item-id"><span>{item.id}</span><span>v{item.version}</span></div>
    <span className="source-chip">{item.copy_type_name}</span>
    <h3>{item.title || presentation.label}</h3>
    {item.progress ? <div className="progress-copy"><Icon name={presentation.icon} /><span>{item.progress}</span></div> : item.body ? <p className="item-excerpt">{item.body}</p> : null}
    {item.findings[0] && <div className="finding-summary"><Icon name="warning" /><span>{item.findings[0].message}</span></div>}
    {item.completion_reason && <span className={`status-chip ${completionPresentation[item.completion_reason].className}`}>{completionPresentation[item.completion_reason].label}</span>}
    <div className="item-metadata"><span>改写 {item.auto_rewrite_count} 次</span>{item.similarity_score !== undefined && <span>相似度 {Math.round(item.similarity_score * 100)}%</span>}<span>{new Date(item.updated_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}</span></div>
    {item.workflow_status === "human_review" && <button className="button button-primary" onClick={(event) => onReview(event.currentTarget)}>审核</button>}
    {item.workflow_status !== "completed" && item.workflow_status !== "human_review" && <button className="button button-small button-text" onClick={onRetry}><Icon name="retry" />单条重试</button>}
  </article>;
}
