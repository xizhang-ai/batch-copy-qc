import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import type { CopyItem, CopyType, GenerationRun, WorkflowStatus } from "../../api/contracts";
import { api } from "../../api/service";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Icon } from "../../components/Icon";
import { Skeleton } from "../../components/Skeleton";
import { ReviewOverlay } from "../review/ReviewOverlay";
import { BoardColumn } from "./BoardColumn";
import { BoardStats } from "./BoardStats";
import { boardViewGroups } from "./statusPresentation";
import { useBoardPolling } from "./useBoardPolling";

export function BoardPage() {
  const { id = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const selectedRunId = params.get("run") || undefined;
  const { data, setData, loading, error, refresh } = useBoardPolling(id, selectedRunId);
  const [reviewItem, setReviewItem] = useState<CopyItem>();
  const [returnFocus, setReturnFocus] = useState<HTMLElement>();
  const [mobileStatus, setMobileStatus] = useState<WorkflowStatus>((params.get("status") as WorkflowStatus) || "pending_ai_qc");
  const [startConfirm, setStartConfirm] = useState(params.get("start") === "confirm");
  const [hideConfirm, setHideConfirm] = useState(false);
  const [batchMutating, setBatchMutating] = useState(false);
  const [typeFilter, setTypeFilter] = useState(params.get("type") || "all");
  const [configuredTypes, setConfiguredTypes] = useState<CopyType[]>([]);
  const [runs, setRuns] = useState<GenerationRun[]>([]);
  const [runsLoading, setRunsLoading] = useState(true);
  const [typeError, setTypeError] = useState("");
  const [batchError, setBatchError] = useState("");
  const startTriggerRef = useRef<HTMLButtonElement>(null);
  const hideTriggerRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);

  const loadTypes = () => {
    setTypeError("");
    api.listCopyTypes(id).then(setConfiguredTypes).catch((err: Error) => setTypeError(`帖子类型加载失败：${err.message}`));
  };
  const loadRuns = () => {
    setBatchError("");
    setRunsLoading(true);
    api.listGenerationRuns(id)
      .then(setRuns)
      .catch((err: Error) => setBatchError(`生成批次加载失败：${err.message}`))
      .finally(() => setRunsLoading(false));
  };
  useEffect(() => {
    let active = true;
    Promise.allSettled([api.listCopyTypes(id), api.listGenerationRuns(id)])
      .then(([typesResult, runsResult]) => {
        if (!active) return;
        if (typesResult.status === "fulfilled") setConfiguredTypes(typesResult.value);
        else setTypeError(`帖子类型加载失败：${(typesResult.reason as Error).message}`);
        if (runsResult.status === "fulfilled") setRuns(runsResult.value);
        else setBatchError(`生成批次加载失败：${(runsResult.reason as Error).message}`);
      })
      .finally(() => { if (active) setRunsLoading(false); });
    return () => { active = false; };
  }, [id]);
  useEffect(() => {
    if (!startConfirm && !hideConfirm) return;
    const returnTarget = startConfirm ? startTriggerRef.current : hideTriggerRef.current;
    const focusableSelector = 'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex="0"]';
    const frame = window.requestAnimationFrame(() => {
      const first = dialogRef.current?.querySelector<HTMLElement>(focusableSelector);
      (first ?? dialogRef.current)?.focus();
    });
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        startConfirm ? setStartConfirm(false) : setHideConfirm(false);
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(focusableSelector));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (document.activeElement === dialogRef.current) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
        return;
      }
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", handler);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", handler);
      returnTarget?.focus();
    };
  }, [hideConfirm, startConfirm]);

  const types = useMemo(() => configuredTypes.length
    ? configuredTypes.map((item) => [item.id, item.name] as const)
    : Array.from(new Map(data?.items.map((item) => [item.copy_type_id, item.copy_type_name]) ?? [])), [configuredTypes, data]);
  const visibleRuns = runs.filter((run) => !run.archived);
  const hiddenRuns = runs.filter((run) => run.archived);
  const selectedRun = runs.find((run) => run.id === data?.run_id) ?? (data?.run_id && data.batch_number ? {
    id: data.run_id,
    project_id: id,
    status: data.run_status === "running" ? "running" as const : "completed" as const,
    total_requested: data.items.length,
    batch_number: data.batch_number,
    label: `第 ${data.batch_number} 批`,
    archived: data.run_archived,
    created_at: data.updated_at,
  } : undefined);
  const nextBatchNumber = Math.max(0, data?.batch_number ?? 0, ...runs.map((run) => run.batch_number)) + 1;
  const filtered = data?.items.filter((item) => typeFilter === "all" || item.copy_type_id === typeFilter) ?? [];
  const updateItem = (updated: CopyItem) => setData(data ? { ...data, items: data.items.map((item) => item.id === updated.id ? updated : item) } : data);
  const retry = async (item: CopyItem) => { try { updateItem(await api.retryQc(item.id)); } catch { /* stale card remains visible */ } };
  const setQueryValue = (key: string, value?: string) => {
    const next = new URLSearchParams(params);
    value ? next.set(key, value) : next.delete(key);
    setParams(next, { replace: true });
  };
  const changeFilter = (value: string) => { setTypeFilter(value); setQueryValue("type", value === "all" ? undefined : value); };
  const changeRun = (value: string) => setQueryValue("run", value || undefined);

  const toggleSelectedRun = async (archived: boolean) => {
    if (!data?.run_id) return;
    setBatchMutating(true);
    setBatchError("");
    try {
      await api.setGenerationRunArchived(data.run_id, archived);
      const nextRuns = await api.listGenerationRuns(id);
      setRuns(nextRuns);
      if (archived) {
        const fallback = nextRuns.find((run) => !run.archived);
        // If this was the only visible batch, keep it explicitly selected so
        // the user immediately sees the hidden state and can restore it.
        changeRun(fallback?.id || data.run_id);
      } else {
        changeRun(data.run_id);
        await refresh();
      }
      setHideConfirm(false);
    } catch (err) {
      setBatchError(`批次操作失败：${(err as Error).message}`);
    } finally {
      setBatchMutating(false);
    }
  };

  return <div className="page board-page">
    <div className="page-header">
      <div>
        <div className="eyebrow">{data?.batch_number ? `第 ${data.batch_number} 批` : "尚无批次"}{data?.run_id ? ` · ${data.run_id}` : ""}</div>
        <h1>文案看板</h1>
        <p className="page-description">每个生成批次独立展示；旧批次可隐藏、查看和恢复，不会丢失 QC 与版本记录。</p>
      </div>
      <div className="header-actions batch-actions">
        <label className="field"><span className="field-label">生成批次</span><select aria-label="生成批次" className="select" value={data?.run_id || ""} onChange={(event) => changeRun(event.target.value)}>
          {!runs.length && <option value="">{runsLoading ? "正在读取批次…" : "暂无批次"}</option>}
          {!!visibleRuns.length && <optgroup label="显示中的批次">{visibleRuns.map((run) => <option value={run.id} key={run.id}>{run.label}{run.id === visibleRuns[0]?.id ? " · 当前" : ""}</option>)}</optgroup>}
          {!!hiddenRuns.length && <optgroup label="已隐藏">{hiddenRuns.map((run) => <option value={run.id} key={run.id}>{run.label} · 已隐藏</option>)}</optgroup>}
        </select></label>
        <label className="field"><span className="field-label">帖子类型</span><select className="select" value={typeFilter} onChange={(event) => changeFilter(event.target.value)}><option value="all">全部类型</option>{types.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
        {selectedRun && <button ref={hideTriggerRef} className={`button ${selectedRun.archived ? "button-secondary" : "button-warning"}`} onClick={() => selectedRun.archived ? void toggleSelectedRun(false) : setHideConfirm(true)} disabled={batchMutating}>{selectedRun.archived ? "恢复本批" : "隐藏本批"}</button>}
        <button ref={startTriggerRef} className="button button-primary button-large" onClick={() => setStartConfirm(true)}><Icon name="plus" />新建第 {nextBatchNumber} 批</button>
      </div>
    </div>
    {error && <ErrorNotice message={`${error}。现有卡片已保留。`} onRetry={refresh} />}
    {typeError && <ErrorNotice message={typeError} onRetry={loadTypes} />}
    {batchError && <ErrorNotice message={batchError} onRetry={loadRuns} />}
    {data?.run_archived && <div className="notice warning batch-archive-notice"><strong>这是已隐藏的第 {data.batch_number} 批。</strong><span>它不会出现在默认看板或默认飞书输出中；需要时可恢复。</span></div>}
    {loading && !data ? <div className="panel section-panel"><Skeleton lines={10} /></div> : data && <>
      <BoardStats board={data} />
      <div className="mobile-status-tabs" role="tablist" aria-label="看板状态">{boardViewGroups.map((group) => <button role="tab" aria-selected={mobileStatus === group.statuses[0]} className={mobileStatus === group.statuses[0] ? "active" : ""} onClick={() => setMobileStatus(group.statuses[0])} key={group.id}>{group.label}<span>{filtered.filter((item) => group.statuses.includes(item.workflow_status)).length}</span></button>)}</div>
      <div className="board-grid">{boardViewGroups.map((group) => <div className={`board-column-wrap${group.statuses.includes(mobileStatus) ? " mobile-active" : ""}`} key={group.id}><BoardColumn group={group} items={filtered.filter((item) => group.statuses.includes(item.workflow_status))} onReview={(item, trigger) => { setReviewItem(item); setReturnFocus(trigger); }} onRetry={retry} /></div>)}</div>
    </>}
    {reviewItem && <ReviewOverlay item={reviewItem} returnFocus={returnFocus} onClose={() => setReviewItem(undefined)} onItemChange={(updated) => { updateItem(updated); setReviewItem(updated.workflow_status === "human_review" ? updated : undefined); }} />}

    {startConfirm && <div className="modal-backdrop"><section ref={dialogRef} tabIndex={-1} className="dialog" role="dialog" aria-modal="true" aria-labelledby="batch-title">
      <div className="batch-dialog-kicker">即将创建 · 第 {nextBatchNumber} 批</div>
      <h2 id="batch-title">按当前规则重新生成</h2>
      <p className="page-description">适合在 Brief、关键词或 QC 规则调整后重新开始。旧批次会完整保留，不会混入新批次看板。</p>
      <div className="notice">{configuredTypes.length > 0 ? configuredTypes.map((type) => <div key={type.id}><strong>{type.name || "未命名帖子类型"} · {type.quantity} 篇</strong></div>) : <strong>正在读取已确认帖子类型…</strong>}<br />预计 {configuredTypes.reduce((sum, type) => sum + type.quantity, 0)} 次生成调用，并逐篇执行确定性与模型 QC。</div>
      <div className="inline-actions" style={{ marginTop: 16 }}><button className="button button-primary" disabled={batchMutating || configuredTypes.length === 0} onClick={async () => {
        setBatchMutating(true); setBatchError("");
        try { const created = await api.createGenerationRun(id); setStartConfirm(false); const nextRuns = await api.listGenerationRuns(id); setRuns(nextRuns); const next = new URLSearchParams(params); next.delete("start"); next.set("run", created.id); setParams(next, { replace: true }); }
        catch (err) { setBatchError(`新建批次失败：${(err as Error).message}`); }
        finally { setBatchMutating(false); }
      }}>{batchMutating ? "正在创建…" : `确认生成第 ${nextBatchNumber} 批`}</button><button className="button button-text" onClick={() => setStartConfirm(false)}>取消</button></div>
    </section></div>}

    {hideConfirm && selectedRun && <div className="modal-backdrop"><section ref={dialogRef} tabIndex={-1} className="dialog" role="dialog" aria-modal="true" aria-labelledby="hide-batch-title">
      <div className="batch-dialog-kicker">{selectedRun.label}</div>
      <h2 id="hide-batch-title">隐藏整批文案？</h2>
      <p className="page-description">隐藏后默认看板只显示上一批；本批文案、版本、QC 和审核记录仍保留，后台处理中任务不会被取消。</p>
      <div className="notice warning"><strong>这不是删除。</strong>你可以随时从“生成批次”菜单选择本批并恢复。</div>
      <div className="inline-actions" style={{ marginTop: 16 }}><button className="button button-warning" disabled={batchMutating} onClick={() => void toggleSelectedRun(true)}>{batchMutating ? "正在隐藏…" : "确认隐藏本批"}</button><button className="button button-text" onClick={() => setHideConfirm(false)}>取消</button></div>
    </section></div>}
  </div>;
}
