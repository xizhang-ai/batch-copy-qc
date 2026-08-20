import { useEffect, useRef, useState } from "react";
import type { QcFinding } from "../../api/contracts";

export function ForcePassDialog({ findings, busy, returnFocus, onSubmit, onClose }: { findings: QcFinding[]; busy: boolean; returnFocus?: HTMLElement; onSubmit: (issues: string, reason: string) => void; onClose: () => void }) {
  const unresolved = findings.filter((finding) => finding.status === "open").map((finding) => `• ${finding.message}`).join("\n");
  const [issues, setIssues] = useState(unresolved);
  const [reason, setReason] = useState("");
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  useEffect(() => {
    const handler = (event: KeyboardEvent) => { if (event.key === "Escape") { event.preventDefault(); event.stopImmediatePropagation(); onCloseRef.current(); } };
    document.addEventListener("keydown", handler);
    return () => { document.removeEventListener("keydown", handler); returnFocus?.focus(); };
  }, [returnFocus]);
  return <div className="modal-backdrop"><section className="dialog" role="dialog" aria-modal="true" aria-labelledby="force-title"><h2 id="force-title">强制通过</h2><div className="notice warning">强制通过会保留遗留问题与放行理由，并在飞书输出中标明完成方式。</div><div className="form-stack" style={{ marginTop: 16 }}><div className="field"><label htmlFor="legacy-issues">遗留问题</label><textarea id="legacy-issues" className="textarea" value={issues} onChange={(event) => setIssues(event.target.value)} /><span className="meta">已自动带入当前未解决问题，可继续修改；不能为空。</span></div><div className="field"><label htmlFor="force-pass-reason">放行理由</label><textarea autoFocus id="force-pass-reason" className="textarea compact" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="说明本次例外放行的负责人判断或业务依据" /><span className="meta">放行理由会独立留痕，不能用遗留问题代替。</span></div></div><div className="inline-actions" style={{ marginTop: 16 }}><button className="button button-warning" disabled={!issues.trim() || !reason.trim() || busy} onClick={() => onSubmit(issues, reason)}>确认强制通过</button><button className="button button-text" onClick={onClose}>取消</button></div></section></div>;
}
