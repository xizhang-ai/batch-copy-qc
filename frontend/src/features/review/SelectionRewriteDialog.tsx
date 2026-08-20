import { useEffect, useRef, useState } from "react";
import type { SelectionState } from "./CopyEditor";

export function SelectionRewriteDialog({ selection, busy, error, returnFocus, onSubmit, onClose }: { selection: SelectionState; busy: boolean; error?: string; returnFocus?: HTMLElement; onSubmit: (instruction: string) => void; onClose: () => void }) {
  const [instruction, setInstruction] = useState("");
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  useEffect(() => {
    const handler = (event: KeyboardEvent) => { if (event.key === "Escape") { event.preventDefault(); event.stopImmediatePropagation(); onCloseRef.current(); } };
    document.addEventListener("keydown", handler);
    return () => { document.removeEventListener("keydown", handler); returnFocus?.focus(); };
  }, [returnFocus]);
  return <div className="modal-backdrop" role="presentation"><section className="dialog" role="dialog" aria-modal="true" aria-labelledby="rewrite-title"><h2 id="rewrite-title">让 AI 定向修改</h2><p className="page-description">只修改选中内容；完成后仍返回人工审核。</p><blockquote className="selection-preview">{selection.text}</blockquote><div className="field"><label htmlFor="rewrite-instruction">修改方向</label><textarea autoFocus id="rewrite-instruction" className="textarea" value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="例如：删除功效暗示，只保留口味体验" /></div>{error && <p role="alert" style={{ color: "var(--danger)" }}>{error}</p>}<div className="inline-actions" style={{ marginTop: 16 }}><button className="button button-primary" disabled={!instruction.trim() || busy} onClick={() => onSubmit(instruction)}>{busy ? "正在修改…" : "提交修改"}</button><button className="button button-text" onClick={onClose}>取消</button></div></section></div>;
}
