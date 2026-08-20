import type { CopyItem, WorkflowStatus } from "../../api/contracts";
import { Icon } from "../../components/Icon";
import { CopyItemCard } from "./CopyItemCard";
import { statusPresentation } from "./statusPresentation";

export function BoardColumn({ status, items, onReview, onRetry }: { status: WorkflowStatus; items: CopyItem[]; onReview: (item: CopyItem, trigger: HTMLButtonElement) => void; onRetry: (item: CopyItem) => void }) {
  const presentation = statusPresentation[status];
  return <section className={`board-column ${presentation.className}`} aria-labelledby={`column-${status}`}><header className="board-column-header"><div><h2 id={`column-${status}`}><Icon name={presentation.icon} />{presentation.label}</h2><p>{presentation.description}</p></div><span className="count-badge">{items.length}</span></header><div className="board-card-list">{items.map((item) => <CopyItemCard key={item.id} item={item} onReview={(trigger) => onReview(item, trigger)} onRetry={() => onRetry(item)} />)}{items.length === 0 && <div className="board-empty">当前没有文案</div>}</div></section>;
}
