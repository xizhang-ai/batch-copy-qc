import { useEffect, useRef, useState } from "react";
import type { CopyItem, ItemResponse, QcFinding, ReviewPayload } from "../../api/contracts";
import { api } from "../../api/service";
import { ApiError } from "../../api/client";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Icon } from "../../components/Icon";
import { CopyEditor, type SelectionState } from "./CopyEditor";
import { ForcePassDialog } from "./ForcePassDialog";
import { QcFindingsPanel } from "./QcFindingsPanel";
import { SelectionRewriteDialog } from "./SelectionRewriteDialog";
import { locateCandidates } from "./findingKeywords";
import { mergeItemResponse } from "./mergeItemResponse";

export function ReviewOverlay({ item, returnFocus, onClose, onItemChange }: { item: CopyItem; returnFocus?: HTMLElement; onClose: () => void; onItemChange: (item: CopyItem) => void }) {
  const [draft, setDraft] = useState(item);
  const [selection, setSelection] = useState<SelectionState>();
  const [rewriteOpen, setRewriteOpen] = useState(false);
  const [forceOpen, setForceOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [locateNote, setLocateNote] = useState("");
  const panelRef = useRef<HTMLElement>(null);
  const titleRef = useRef<HTMLTextAreaElement>(null);
  const bodyRef = useRef<HTMLTextAreaElement>(null);
  const tagRef = useRef<HTMLInputElement>(null);
  const rewriteTriggerRef = useRef<HTMLButtonElement>(null);
  const forceTriggerRef = useRef<HTMLButtonElement>(null);
  useEffect(() => { panelRef.current?.focus(); return () => returnFocus?.focus(); }, [returnFocus]);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") { if (rewriteOpen || forceOpen) return; event.preventDefault(); onClose(); }
      if (event.key === "Tab" && panelRef.current) {
        const focusable = Array.from(panelRef.current.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex="0"]'));
        if (!focusable.length) return; const first = focusable[0]; const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", handler); return () => document.removeEventListener("keydown", handler);
  }, [forceOpen, onClose, rewriteOpen]);
  const mergeResponse = async (current: CopyItem, response: ItemResponse) => {
    let merged = mergeItemResponse(current, response);
    if (!Array.isArray(response.findings)) {
      try { merged = mergeItemResponse(merged, await api.getItem(current.id)); }
      catch { setError("修改已生效，但最新 QC 结果加载失败。请关闭后重新打开审核面板。"); }
    }
    return merged;
  };
  const save = async () => { setBusy(true); setError(""); try { const updated = await mergeResponse(draft, await api.saveItem(draft.id, { title: draft.title, body: draft.body, tags: draft.tags, version: draft.version })); setDraft(updated); onItemChange(updated); } catch (err) { setError((err as Error).message); } finally { setBusy(false); } };
  const review = async (action: "reject" | "pass" | "force_pass", details: Pick<ReviewPayload, "reason" | "legacy_issues"> = {}) => { setBusy(true); setError(""); try { const updated = await mergeResponse(draft, await api.reviewItem(draft.id, { action, ...details })); onItemChange(updated); if (action !== "reject") onClose(); else setDraft(updated); } catch (err) { setError((err as Error).message); } finally { setBusy(false); } };
  const rewrite = async (instruction: string) => { if (!selection) return; setBusy(true); setError(""); try { const updated = await mergeResponse(draft, await api.rewriteSelection(draft.id, { expected_version: draft.version, selected_text: selection.text, selection_start: selection.start, selection_end: selection.end, field: selection.field, instruction })); setDraft(updated); onItemChange(updated); setRewriteOpen(false); setSelection(undefined); } catch (err) { const message = err instanceof ApiError && err.status === 409 ? `${err.message}。你的编辑内容已保留。` : (err as Error).message; setError(message); } finally { setBusy(false); } };
  const locate = (finding: QcFinding) => {
    const targets = [
      { field: "title", label: "标题", ref: titleRef.current },
      { field: "body", label: "正文", ref: bodyRef.current },
      { field: "tags", label: "话题标签", ref: tagRef.current },
    ];
    const ordered = finding.field
      ? [...targets.filter((target) => target.field === finding.field), ...targets.filter((target) => target.field !== finding.field)]
      : targets;
    for (const keyword of locateCandidates(finding)) {
      for (const target of ordered) {
        if (!target.ref) continue;
        const start = target.ref.value.toLocaleLowerCase().indexOf(keyword.toLocaleLowerCase());
        if (start < 0) continue;
        target.ref.focus();
        target.ref.setSelectionRange(start, start + keyword.length);
        if (typeof target.ref.scrollIntoView === "function") {
          target.ref.scrollIntoView({ block: "center", behavior: "smooth" });
        }
        setLocateNote(`已定位${target.label}中的关键词：“${keyword}”`);
        return;
      }
    }
    if (bodyRef.current && typeof bodyRef.current.scrollIntoView === "function") {
      bodyRef.current.scrollIntoView({ block: "center", behavior: "smooth" });
    }
    setLocateNote("当前版本中未找到相同关键词，可能已经被修改；请结合完整证据人工核对。");
  };
  const unresolvedHard = draft.findings.some((finding) => finding.level === "hard" && finding.status === "open" && (draft.title.includes(finding.evidence) || draft.body.includes(finding.evidence)));
  return <div className="review-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }}>
    <section ref={panelRef} className="review-panel" role="dialog" aria-modal="true" aria-labelledby="review-dialog-title" tabIndex={-1}>
      <div className="review-top"><header className="review-header"><div><div className="eyebrow">{draft.id} · {draft.copy_type_name} · 版本 {draft.version}</div><h1 id="review-dialog-title">人工审核</h1></div><button className="button button-secondary icon-button" aria-label="关闭人工审核" onClick={onClose}><Icon name="close" /></button></header>{error && <div className="review-feedback"><ErrorNotice message={error} /></div>}{locateNote && <div className="review-feedback"><div className="notice locate-feedback" role="status">{locateNote}</div></div>}</div>
      <div className="review-layout"><div className="review-left"><CopyEditor value={draft} onChange={setDraft} onSelection={setSelection} titleRef={titleRef} bodyRef={bodyRef} tagRef={tagRef} />{selection && <button ref={rewriteTriggerRef} className="selection-action" onClick={() => setRewriteOpen(true)}><Icon name="spark" />让 AI 修改 <kbd>Ctrl ⇧ M</kbd></button>}</div><aside className="review-right"><QcFindingsPanel findings={draft.findings} onLocate={locate} /><div className="divider" /><h2>修改记录</h2><ol className="history-list"><li><strong>v{draft.version}</strong><span>当前人工审核版本</span></li><li><strong>v{Math.max(1, draft.version - 1)}</strong><span>AI 自动修改 · {draft.auto_rewrite_count} 次</span></li><li><strong>v1</strong><span>批量生成初稿</span></li></ol></aside></div>
      <footer className="review-actions"><button className="button button-secondary" disabled={busy} onClick={save}>保存修改</button><button className="button button-danger" disabled={busy} onClick={() => review("reject")}>未通过</button><button ref={forceTriggerRef} className="button button-warning" disabled={busy} onClick={() => setForceOpen(true)}>强制通过</button><button className="button button-primary button-large" title={unresolvedHard ? "仍有未解决硬规则" : ""} disabled={busy || unresolvedHard} onClick={() => review("pass")}>正常通过</button></footer>
      {selection && rewriteOpen && <SelectionRewriteDialog selection={selection} busy={busy} error={error} returnFocus={rewriteTriggerRef.current ?? undefined} onSubmit={rewrite} onClose={() => setRewriteOpen(false)} />}
      {forceOpen && <ForcePassDialog findings={draft.findings} busy={busy} returnFocus={forceTriggerRef.current ?? undefined} onSubmit={(issues, reason) => review("force_pass", { reason: reason.trim(), legacy_issues: issues.split(/\r?\n/).map((issue) => issue.replace(/^\s*[•*-]\s*/, "").trim()).filter(Boolean) })} onClose={() => setForceOpen(false)} />}
    </section>
  </div>;
}
