import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import type { ConnectionStatus as ConnectionStatusType, ExportPreview, ExportRun } from "../../api/contracts";
import { api } from "../../api/service";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Icon } from "../../components/Icon";
import { Skeleton } from "../../components/Skeleton";
import { ConnectionStatus } from "./ConnectionStatus";
import { ExportHistory } from "./ExportHistory";

export function ExportPage() {
  const { id = "" } = useParams();
  const [connections, setConnections] = useState<ConnectionStatusType>();
  const [preview, setPreview] = useState<ExportPreview>();
  const [history, setHistory] = useState<ExportRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = () => { setLoading(true); Promise.all([api.getConnections(), api.getExportPreview(id), api.listExports(id)]).then(([nextConnections, nextPreview, nextHistory]) => { setConnections(nextConnections); setPreview(nextPreview); setHistory(nextHistory); }).catch((err: Error) => setError(err.message)).finally(() => setLoading(false)); };
  useEffect(load, [id]);
  useEffect(() => {
    const active = history.filter((item) => item.status === "pending" || item.status === "running");
    if (!active.length) return;
    const timer = window.setInterval(async () => {
      const updates = await Promise.all(active.map((item) => api.getExportRun(item.id)));
      setHistory((current) => current.map((item) => updates.find((next) => next.id === item.id) ?? item));
    }, 2000);
    return () => window.clearInterval(timer);
  }, [history]);
  const create = async () => { setBusy(true); setError(""); try { const run = await api.createExport(id); setHistory([run, ...history]); } catch (err) { setError((err as Error).message); } finally { setBusy(false); } };
  const retry = async (item: ExportRun) => { setBusy(true); try { const next = await api.retryExport(item.id); setHistory(history.map((entry) => entry.id === next.id ? next : entry)); } catch (err) { setError((err as Error).message); } finally { setBusy(false); } };
  return <div className="page export-page">
    <div className="page-header"><div><h1>飞书输出</h1><p className="page-description">仅输出已完成文案。真实凭证由服务端环境变量管理，前端只显示只读状态。</p></div></div>
    {error && <ErrorNotice message={error} onRetry={load} />}
    {loading || !connections || !preview ? <div className="panel section-panel"><Skeleton lines={10} /></div> : <>
      <ConnectionStatus value={connections} />
      <section className="export-preview panel section-panel"><div className="preview-main"><div className="eyebrow">本次输出预览</div><strong className="preview-count">{preview.completed}</strong><span>篇已完成文案</span><div className="reason-grid"><span>AI 自动通过<strong>{preview.by_reason.ai_pass}</strong></span><span>人工通过<strong>{preview.by_reason.human_pass}</strong></span><span>强制通过<strong>{preview.by_reason.forced_pass}</strong></span></div></div><div className="preview-detail"><h2>固定列</h2><div className="chip-row">{preview.columns.map((column) => <span className="source-chip" key={column}>{column}</span>)}</div><div className="notice warning" style={{ marginTop: 16 }}>本次排除：待人工 {preview.excluded_human_review} 篇，未通过 {preview.excluded_rejected} 篇。</div><button className="button button-primary button-large" disabled={busy || preview.completed === 0} onClick={create}><Icon name="export" />{busy ? "正在输出…" : connections.feishu.adapter.toLowerCase().includes("fake") ? "使用模拟输出" : connections.feishu.configured ? "输出到飞书" : "飞书未配置"}</button></div></section>
      <ExportHistory items={history} onRetry={retry} />
    </>}
  </div>;
}
