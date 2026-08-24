import type { CopyItem } from "../../api/contracts";
import { Icon } from "../../components/Icon";
import { CopyItemCard } from "./CopyItemCard";
import type { BoardViewGroup } from "./statusPresentation";

export function BoardColumn({ group, items, onReview, onRetry }: { group: BoardViewGroup; items: CopyItem[]; onReview: (item: CopyItem, trigger: HTMLButtonElement) => void; onRetry: (item: CopyItem) => void }) {
  return <section className={`board-column ${group.className}`} aria-labelledby={`column-${group.id}`}><header className="board-column-header"><div><h2 id={`column-${group.id}`}><Icon name={group.icon} />{group.label}</h2><p>{group.description}</p></div><span className="count-badge">{items.length}</span></header><div className="board-card-list">{items.map((item) => <CopyItemCard key={item.id} item={item} onReview={(trigger) => onReview(item, trigger)} onRetry={() => onRetry(item)} />)}{items.length === 0 && <div className="board-empty">当前没有文案</div>}</div></section>;
}
