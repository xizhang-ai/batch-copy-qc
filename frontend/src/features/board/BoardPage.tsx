import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import type { CopyItem, CopyType, WorkflowStatus } from "../../api/contracts";
import { api } from "../../api/service";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Icon } from "../../components/Icon";
import { Skeleton } from "../../components/Skeleton";
import { ReviewOverlay } from "../review/ReviewOverlay";
import { BoardColumn } from "./BoardColumn";
import { BoardStats } from "./BoardStats";
import { boardStatuses, statusPresentation } from "./statusPresentation";
import { useBoardPolling } from "./useBoardPolling";

export function BoardPage() {
  const { id = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const { data, setData, loading, error, refresh } = useBoardPolling(id);
  const [reviewItem, setReviewItem] = useState<CopyItem>();
  const [returnFocus, setReturnFocus] = useState<HTMLElement>();
  const [mobileStatus, setMobileStatus] = useState<WorkflowStatus>((params.get("status") as WorkflowStatus) || "pending_ai_qc");
  const [startConfirm, setStartConfirm] = useState(params.get("start") === "confirm");
  const [starting, setStarting] = useState(false);
  const [typeFilter, setTypeFilter] = useState(params.get("type") || "all");
  const [configuredTypes, setConfiguredTypes] = useState<CopyType[]>([]);
  const [typeError, setTypeError] = useState("");
  const retryTypes = () => { setTypeError(""); api.listCopyTypes(id).then(setConfiguredTypes).catch((err: Error) => setTypeError(`帖子类型加载失败：${err.message}`)); };
  useEffect(() => { let active = true; api.listCopyTypes(id).then((items) => { if (active) setConfiguredTypes(items); }).catch((err: Error) => { if (active) setTypeError(`帖子类型加载失败：${err.message}`); }); return () => { active = false; }; }, [id]);
  const types = useMemo(() => configuredTypes.length ? configuredTypes.map((item) => [item.id, item.name] as const) : Array.from(new Map(data?.items.map((item) => [item.copy_type_id, item.copy_type_name]) ?? [])), [configuredTypes, data]);
  const filtered = data?.items.filter((item) => typeFilter === "all" || item.copy_type_id === typeFilter) ?? [];
  const updateItem = (updated: CopyItem) => setData(data ? { ...data, items: data.items.map((item) => item.id === updated.id ? updated : item) } : data);
  const retry = async (item: CopyItem) => { try { updateItem(await api.retryQc(item.id)); } catch { /* global stale data remains visible */ } };
  const changeFilter = (value: string) => { setTypeFilter(value); const next = new URLSearchParams(params); value === "all" ? next.delete("type") : next.set("type", value); setParams(next, { replace: true }); };
  return <div className="page board-page">
    <div className="page-header"><div><div className="eyebrow">运行 {data?.run_id || "—"}</div><h1>文案看板</h1><p className="page-description">固定五列由状态机自动流转。P0 不支持跨列拖动。</p></div><div className="header-actions"><label className="field"><span className="field-label">帖子类型</span><select className="select" value={typeFilter} onChange={(event) => changeFilter(event.target.value)}><option value="all">全部类型</option>{types.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><button className="button button-primary button-large" onClick={() => setStartConfirm(true)}><Icon name="plus" />新生成批次</button></div></div>
    {error && <ErrorNotice message={`${error}。现有卡片已保留。`} onRetry={refresh} />}{typeError && <ErrorNotice message={typeError} onRetry={retryTypes} />}
    {loading && !data ? <div className="panel section-panel"><Skeleton lines={10} /></div> : data && <><BoardStats board={data} /><div className="mobile-status-tabs" role="tablist" aria-label="看板状态">{boardStatuses.map((status) => <button role="tab" aria-selected={mobileStatus === status} className={mobileStatus === status ? "active" : ""} onClick={() => setMobileStatus(status)} key={status}>{statusPresentation[status].label}<span>{filtered.filter((item) => item.workflow_status === status).length}</span></button>)}</div><div className="board-grid">{boardStatuses.map((status) => <div className={`board-column-wrap${mobileStatus === status ? " mobile-active" : ""}`} key={status}><BoardColumn status={status} items={filtered.filter((item) => item.workflow_status === status)} onReview={(item, trigger) => { setReviewItem(item); setReturnFocus(trigger); }} onRetry={retry} /></div>)}</div></>}
    {reviewItem && <ReviewOverlay item={reviewItem} returnFocus={returnFocus} onClose={() => setReviewItem(undefined)} onItemChange={(updated) => { updateItem(updated); setReviewItem(updated.workflow_status === "human_review" ? updated : undefined); }} />}
    {startConfirm && <div className="modal-backdrop"><section className="dialog" role="dialog" aria-modal="true" aria-labelledby="batch-title"><h2 id="batch-title">确认新生成批次</h2><p className="page-description">将按当前已确认类型与 QC 快照生成。现有批次不会被覆盖。</p><div className="notice">{configuredTypes.length > 0 ? configuredTypes.map((type) => <div key={type.id}><strong>{type.name || "未命名帖子类型"} · {type.quantity} 篇</strong></div>) : <strong>正在读取已确认帖子类型…</strong>}<br />预计 {configuredTypes.reduce((sum, type) => sum + type.quantity, 0)} 次生成调用，并逐篇执行确定性与模型 QC。</div><div className="inline-actions" style={{ marginTop: 16 }}><button className="button button-primary" disabled={starting || configuredTypes.length === 0} onClick={async () => { setStarting(true); try { await api.createGenerationRun(id); setStartConfirm(false); const next = new URLSearchParams(params); next.delete("start"); setParams(next, { replace: true }); await refresh(); } finally { setStarting(false); } }}>{starting ? "正在创建…" : "确认开始"}</button><button className="button button-text" onClick={() => setStartConfirm(false)}>取消</button></div></section></div>}
  </div>;
}
