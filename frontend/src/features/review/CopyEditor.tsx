import type { RefObject } from "react";
import type { CopyItem } from "../../api/contracts";
import { Icon } from "../../components/Icon";

export interface SelectionState { field: "title" | "body"; text: string; start: number; end: number }

export function CopyEditor({ value, onChange, onSelection, titleRef, bodyRef }: { value: CopyItem; onChange: (value: CopyItem) => void; onSelection: (selection?: SelectionState) => void; titleRef: RefObject<HTMLInputElement | null>; bodyRef: RefObject<HTMLTextAreaElement | null> }) {
  const normalizeTag = (tag: string) => tag.trim().replace(/^#+/, "");
  const capture = (field: "title" | "body", target: HTMLInputElement | HTMLTextAreaElement) => {
    const start = target.selectionStart ?? 0; const end = target.selectionEnd ?? 0;
    onSelection(end > start ? { field, text: target.value.slice(start, end), start, end } : undefined);
  };
  const context = (event: React.MouseEvent<HTMLInputElement | HTMLTextAreaElement>, field: "title" | "body") => { const target = event.currentTarget; if ((target.selectionEnd ?? 0) > (target.selectionStart ?? 0)) { event.preventDefault(); capture(field, target); } };
  return <div className="copy-editor form-stack">
    <div className="field"><label htmlFor="review-title">标题</label><input ref={titleRef} id="review-title" className="input title-input" value={value.title} onChange={(event) => onChange({ ...value, title: event.target.value })} onSelect={(event) => capture("title", event.currentTarget)} onContextMenu={(event) => context(event, "title")} /></div>
    <div className="field"><label htmlFor="review-body">正文</label><textarea ref={bodyRef} id="review-body" className="textarea review-body" value={value.body} onChange={(event) => onChange({ ...value, body: event.target.value })} onSelect={(event) => capture("body", event.currentTarget)} onContextMenu={(event) => context(event, "body")} onKeyDown={(event) => { if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "m") capture("body", event.currentTarget); }} /></div>
    <div className="field"><label htmlFor="review-tags">话题标签</label><div className="chip-input"><Icon name="plus" /><input id="review-tags" value={value.tags.map(normalizeTag).join("、")} onChange={(event) => onChange({ ...value, tags: event.target.value.split(/[、,#\s]+/).map(normalizeTag).filter(Boolean) })} placeholder="输入标签文字，用空格或顿号分隔；# 会自动添加" /></div><div className="chip-row">{value.tags.map(normalizeTag).filter(Boolean).map((tag) => <span className="source-chip" key={tag}>#{tag}</span>)}</div></div>
  </div>;
}
