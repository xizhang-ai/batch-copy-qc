import type { TypeBriefReview as TypeBriefReviewValue, TypeBriefReviewDecision, TypeBriefReviewItem } from "../../api/contracts";

const decisionLabels: Record<TypeBriefReviewDecision, string> = {
  pending: "待处理",
  confirmed: "已确认",
  ignored: "已忽略",
};

function ReviewGroup({
  title,
  description,
  items,
  onChange,
}: {
  title: string;
  description: string;
  items: TypeBriefReviewItem[];
  onChange: (items: TypeBriefReviewItem[]) => void;
}) {
  const update = (id: string, patch: Partial<TypeBriefReviewItem>) => onChange(items.map((item) => item.id === id ? { ...item, ...patch } : item));
  return <section className="brief-review-group" aria-label={title}>
    <div className="section-heading"><div><h3>{title}<span className="count-badge">{items.length}</span></h3><p className="page-description">{description}</p></div></div>
    {items.length === 0 ? <p className="meta">没有识别到此类内容。</p> : <div className="brief-review-list">{items.map((item, index) => <article className="surface-card brief-review-card" key={item.id}>
      <div className="brief-review-card-header"><span className="source-chip">{item.section || `条目 ${index + 1}`}</span><span className={`status-chip ${item.decision === "confirmed" ? "success" : item.decision === "ignored" ? "warning" : ""}`}>{decisionLabels[item.decision]}</span></div>
      <div className="field"><label htmlFor={`${item.id}-value`}>识别内容</label><textarea id={`${item.id}-value`} className="textarea compact" value={item.value} onChange={(event) => update(item.id, { value: event.target.value })} /></div>
      <div className="field"><label htmlFor={`${item.id}-evidence`}>原文依据</label><textarea id={`${item.id}-evidence`} className="textarea compact" value={item.source_quote} onChange={(event) => update(item.id, { source_quote: event.target.value })} /></div>
      <div className="brief-review-card-footer"><span className="meta">模型置信度 {Math.round(item.confidence * 100)}%</span><div className="inline-actions"><button type="button" className="button button-small button-secondary" aria-pressed={item.decision === "confirmed"} onClick={() => update(item.id, { decision: "confirmed" })}>确认保留</button><button type="button" className="button button-small button-text" aria-pressed={item.decision === "ignored"} onClick={() => update(item.id, { decision: "ignored" })}>忽略</button>{item.decision !== "pending" && <button type="button" className="button button-small button-text" onClick={() => update(item.id, { decision: "pending" })}>恢复待处理</button>}</div></div>
    </article>)}</div>}
  </section>;
}

export function TypeBriefReview({ value, onChange }: { value: TypeBriefReviewValue; onChange: (value: TypeBriefReviewValue) => void }) {
  return <section className="panel section-panel brief-review" aria-labelledby="type-brief-review-title">
    <div className="section-heading"><div><div className="eyebrow">类型 Brief 审阅</div><h2 id="type-brief-review-title">逐条确认项目事实建议与冲突</h2><p className="page-description">这里只记录是否采纳，不会自动覆盖项目内容。修改与处理结果会随帖子类型一起保存。</p></div></div>
    <div className="brief-review-grid">
      <ReviewGroup title="项目事实建议" description="可能影响品牌、SKU、价格或产品事实，确认后仍需回到项目内容正式修改。" items={value.project_change_suggestions} onChange={(items) => onChange({ ...value, project_change_suggestions: items })} />
      <ReviewGroup title="冲突与待确认" description="模型无法归类或与已有要求可能冲突的内容，请确认保留或明确忽略。" items={value.conflicts} onChange={(items) => onChange({ ...value, conflicts: items })} />
    </div>
  </section>;
}
