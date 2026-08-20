import { useState } from "react";
import type { CopyType, TypeBriefReviewItem } from "../../api/contracts";
import { api } from "../../api/service";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Icon } from "../../components/Icon";
import { ReferenceExamplesEditor } from "./ReferenceExamplesEditor";
import { TypeBriefReview } from "./TypeBriefReview";
import { TypeConstraintsEditor } from "./TypeConstraintsEditor";

function normalizeReviewItem(item: Partial<TypeBriefReviewItem>, index: number, kind: string): TypeBriefReviewItem {
  return {
    id: item.id || `${kind}-${crypto.randomUUID()}-${index}`,
    section: item.section || "待确认",
    value: String(item.value ?? ""),
    source_quote: String(item.source_quote ?? ""),
    confidence: typeof item.confidence === "number" ? item.confidence : 0,
    decision: item.decision || "pending",
  };
}

export function CopyTypeEditor({ initial, onSaved, onDelete }: { initial: CopyType; onSaved: (value: CopyType) => void; onDelete: () => void }) {
  const [value, setValue] = useState(initial);
  const [tab, setTab] = useState<"basis" | "constraints">("basis");
  const [saving, setSaving] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");
  const [briefNotice, setBriefNotice] = useState("");
  const toggleMode = (mode: CopyType["input_modes"][number]) => setValue({ ...value, input_modes: value.input_modes.includes(mode) ? value.input_modes.filter((item) => item !== mode) : [...value.input_modes, mode] });
  const analyze = async () => { setAnalyzing(true); setError(""); try { setValue({ ...value, reference_profile: await api.analyzeReferences(value.id, value.references) }); } catch (err) { setError((err as Error).message); } finally { setAnalyzing(false); } };
  const save = async () => { setSaving(true); setError(""); try { const result = await api.saveCopyType(value); if (value.brief_review && !result.brief_review) throw new Error("服务端尚未保存类型 Brief 审阅结果，请稍后重试或联系管理员。当前修改仍保留在页面中。"); setValue(result); onSaved(result); } catch (err) { setError((err as Error).message); } finally { setSaving(false); } };
  const parseBrief = async (file?: File) => { if (!value.type_brief.trim() && !file) return; setAnalyzing(true); setBriefNotice(""); try { const patch = await api.parseCopyTypeBrief(value.id, { text: value.type_brief, file }); const parsedReview = patch.brief_review ?? { project_change_suggestions: patch.project_change_suggestions ?? [], conflicts: patch.conflicts ?? [] }; const briefReview = { project_change_suggestions: parsedReview.project_change_suggestions.map((item, index) => normalizeReviewItem(item, index, "project")), conflicts: parsedReview.conflicts.map((item, index) => normalizeReviewItem(item, index, "conflict")) }; setValue({ ...value, ...patch, requirements: patch.requirements ?? value.requirements, must_include: patch.must_include?.length ? patch.must_include : value.must_include, must_avoid: patch.must_avoid?.length ? patch.must_avoid : value.must_avoid, sources: Array.from(new Set([...value.sources, ...(patch.sources ?? [])])), brief_review: briefReview }); const notes = [`已拆出 ${patch.parsed_finding_count ?? "若干"} 项，可继续修改类型字段。`, `${briefReview.project_change_suggestions.length} 项项目事实建议、${briefReview.conflicts.length} 项冲突已列在下方，请逐条处理。`]; setBriefNotice(notes.join(" ")); } catch (err) { setError((err as Error).message); } finally { setAnalyzing(false); } };
  const valid = value.name.trim() && value.quantity > 0 && value.input_modes.length > 0 && (!value.input_modes.includes("reference_examples") || (value.references.some((item) => item.body.trim()) && value.reference_profile?.confirmed));
  return <section className="type-editor">
    {error && <ErrorNotice message={error} />}
    <div className="panel section-panel form-stack">
      <div className="form-grid"><div className="field"><label htmlFor="type-name">帖子类型名称</label><input id="type-name" className="input" value={value.name} onChange={(event) => setValue({ ...value, name: event.target.value })} placeholder="由你定义，不使用系统预设" /></div><div className="field"><label htmlFor="type-quantity">生成数量</label><input id="type-quantity" type="number" min="1" max="100" className="input numeric" value={value.quantity} onChange={(event) => setValue({ ...value, quantity: Number(event.target.value) })} /><span className="meta">单类型 1–100 篇；生成前会汇总项目总量。</span></div></div>
      <div className="field"><label htmlFor="type-brief">类型 Brief（可选）</label><textarea id="type-brief" className="textarea" value={value.type_brief} onChange={(event) => setValue({ ...value, type_brief: event.target.value })} placeholder="粘贴一段类型说明，或直接在下面组合依据。" /><div className="inline-actions"><button className="button button-small button-secondary" disabled={analyzing || !value.type_brief.trim()} onClick={() => parseBrief()}><Icon name="spark" />识别类型 Brief</button><label className="button button-small button-secondary" htmlFor={`type-brief-file-${value.id}`}><Icon name="file" />上传类型 Brief</label><input id={`type-brief-file-${value.id}`} hidden type="file" accept=".txt,.md,.docx" onChange={(event) => parseBrief(event.target.files?.[0])} /></div>{briefNotice && <div className="notice" role="status">{briefNotice}</div>}</div>
      <div><span className="field-label">组合依据（至少选择一种）</span><div className="form-grid" style={{ marginTop: 8 }}><label className="check-row"><input type="checkbox" checked={value.input_modes.includes("reference_examples")} onChange={() => toggleMode("reference_examples")} /><span><strong>参考案例</strong><br /><small>保留 1–5 篇完整原帖，并分析可编辑风格画像。</small></span></label><label className="check-row"><input type="checkbox" checked={value.input_modes.includes("description_requirements")} onChange={() => toggleMode("description_requirements")} /><span><strong>描述要求</strong><br /><small>补充标题、结构、语气、人设、场景和话题要求。</small></span></label></div></div>
    </div>
    <div className="section-tabs" role="tablist" aria-label="帖子类型编辑区"><button className={`button ${tab === "basis" ? "button-primary" : "button-text"}`} onClick={() => setTab("basis")}>依据输入与风格画像</button><button className={`button ${tab === "constraints" ? "button-primary" : "button-text"}`} onClick={() => setTab("constraints")}>描述要求与默认 QC</button></div>
    {tab === "basis" && (value.input_modes.includes("reference_examples") ? <ReferenceExamplesEditor value={value} analyzing={analyzing} onChange={setValue} onAnalyze={analyze} /> : <div className="panel section-panel"><p className="page-description">当前未启用参考案例。可只用描述要求建立这个帖子类型。</p></div>)}
    {value.brief_review && <TypeBriefReview value={value.brief_review} onChange={(briefReview) => setValue({ ...value, brief_review: briefReview })} />}
    {tab === "constraints" && <div className="panel section-panel"><TypeConstraintsEditor value={value} onChange={setValue} /></div>}
    <div className="sticky-save"><button className="button button-text" onClick={onDelete}><Icon name="trash" />删除类型</button><span className="meta">{valid ? "可以保存并用于生成" : "请完成名称、依据和参考画像确认"}</span><button className="button button-primary button-large" disabled={!valid || saving} onClick={save}>{saving ? "保存中…" : "保存帖子类型"}</button></div>
  </section>;
}
