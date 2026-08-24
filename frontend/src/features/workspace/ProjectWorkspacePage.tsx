import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { AssistantPlan, AssistantSession, CopyType, GenerationRun, ParsedBrief, Project } from "../../api/contracts";
import { api } from "../../api/service";
import { ErrorNotice } from "../../components/ErrorNotice";
import { BriefInputPanel } from "../project-content/BriefInputPanel";

function nextStep(project: Project | undefined, types: CopyType[], run: GenerationRun | undefined) {
  if (run?.generation_phase === "awaiting_preview_approval") return "确认预览方向";
  if (run?.generation_phase === "full_running") return "系统正在生成文案";
  if (run?.generation_phase === "completed") return "查看已完成文案";
  if (!project?.status || project.status === "draft") return "描述你的任务";
  if (!types.length) return "确定内容方向";
  return "先生成 3 篇预览";
}

export function ProjectWorkspacePage() {
  const { id = "" } = useParams();
  const [project, setProject] = useState<Project>();
  const [types, setTypes] = useState<CopyType[]>([]);
  const [session, setSession] = useState<AssistantSession>();
  const [run, setRun] = useState<GenerationRun>();
  const [input, setInput] = useState("");
  const [plan, setPlan] = useState<AssistantPlan>();
  const [briefPanelOpen, setBriefPanelOpen] = useState(false);
  const [parsedBrief, setParsedBrief] = useState<ParsedBrief>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const loadVersion = useRef(0);
  const load = async () => {
    const requestVersion = ++loadVersion.current;
    setError("");
    try {
      const [nextProject, nextTypes, nextSession, runs] = await Promise.all([api.getProject(id), api.listCopyTypes(id), api.getAssistantSession(id), api.listGenerationRuns(id)]);
      if (requestVersion !== loadVersion.current) return;
      setProject(nextProject); setTypes(nextTypes); setSession(nextSession); setRun(runs[0]);
    } catch (err) { if (requestVersion === loadVersion.current) setError((err as Error).message); }
  };
  useEffect(() => { void load(); }, [id]);
  const step = useMemo(() => nextStep(project, types, run), [project, run, types]);
  const send = async () => {
    if (!input.trim()) return;
    setBusy(true); setError("");
    try { const response = await api.sendAssistantMessage(id, input.trim()); await load(); setPlan(response.plan); setInput(""); }
    catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  };
  const parseBrief = async (input: { text?: string; file?: File }) => {
    setBusy(true); setError("");
    try { setParsedBrief(await api.parseProjectBrief(id, input)); }
    catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  };
  const applyBrief = async () => {
    if (!parsedBrief) return;
    setBusy(true); setError("");
    try { setProject(await api.saveProjectFindings(id, parsedBrief)); setParsedBrief(undefined); setBriefPanelOpen(false); }
    catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  };
  const apply = async () => {
    if (!plan) return;
    setBusy(true); setError("");
    try { await api.applyAssistantActions(id, plan.actions); await load(); setPlan(undefined); }
    catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  };
  const start = async (mode: "preview" | "full") => {
    setBusy(true); setError("");
    try { const created = await api.createGenerationRun(id, mode); setRun(created); }
    catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  };
  const confirmPreview = async () => {
    if (!run?.preview_item_count) return;
    setBusy(true); setError("");
    try { const confirmed = await api.confirmPreview(run.id, run.preview_item_count); setRun(confirmed); }
    catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  };
  const remaining = Math.max(0, (run?.total_requested ?? 0) - (run?.preview_item_count ?? 0));

  return <div className="page workspace-page">
    <div className="workspace-heading"><div><div className="eyebrow">任务工作台</div><h1>{project?.name || "正在打开任务"}</h1><p className="page-description">上传 Brief 或直接描述需求；完整的项目、类型、规则、审核和输出能力都保留在高级配置中。</p></div><div className="inline-actions"><button className="button button-secondary" onClick={() => setBriefPanelOpen((open) => !open)}>上传 Brief</button><Link className="button button-secondary" to={`/projects/${id}/content`}>完整 Brief 编辑</Link><Link className="button button-secondary" to={`/projects/${id}/types`}>高级配置</Link><Link className="button button-secondary" to={`/projects/${id}/board`}>查看全部文案</Link></div></div>
    {error && <ErrorNotice message={error} onRetry={load} />}
    {briefPanelOpen && <div className="workspace-brief"><BriefInputPanel busy={busy} onParse={(input) => void parseBrief(input)} />{parsedBrief && <section className="panel section-panel brief-confirmation"><div><strong>已从 {parsedBrief.source_name} 拆出 {parsedBrief.findings.length} 项项目内容与约束。</strong><p className="meta">确认后会写入原有项目内容、文案要求和 QC 逻辑；也可以先进入完整编辑页逐条调整。</p></div><div className="inline-actions"><Link className="button button-secondary" to={`/projects/${id}/content`}>逐条编辑</Link><button className="button button-primary" disabled={busy} onClick={() => void applyBrief()}>确认并写入项目</button></div></section>}</div>}
    <div className="workspace-grid">
      <section className="assistant-panel" aria-label="任务助手"><div className="assistant-panel-head"><div><div className="eyebrow">任务助手</div><h2>告诉我你想做什么</h2></div><span className="status-chip">对话会同步任务状态</span></div><div className="assistant-transcript" aria-live="polite">{session?.messages.length ? session.messages.map((message) => <article className={`assistant-message ${message.role}`} key={message.id}><span>{message.role === "user" ? "你" : message.role === "assistant" ? "助手" : "系统"}</span><p>{message.content}</p></article>) : <div className="assistant-welcome"><strong>例如：</strong><p>“给新品做 20 篇通勤场景种草，语气自然一点，别写夸大功效。”</p></div>}</div>{plan && <section className="assistant-plan-card"><div className="eyebrow">我准备这样做</div><p>{plan.summary}</p>{plan.assumptions.map((item) => <div className="meta" key={item}>假设：{item}</div>)}{plan.blockers.map((item) => <div className="notice warning" key={item}>{item}</div>)}<button className="button button-primary" disabled={busy || !!plan.blockers.length} onClick={() => void apply()}>应用到任务</button></section>}<div className="assistant-composer"><textarea className="textarea" aria-label="告诉我你想做什么" value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) { event.preventDefault(); void send(); } }} placeholder="例如：做 20 篇通勤场景文案，先给我看 3 篇预览" /><div className="inline-actions"><span className="meta">Ctrl / ⌘ + Enter 发送</span><button className="button button-primary" disabled={busy || !input.trim()} onClick={() => void send()}>{busy ? "处理中…" : "发送"}</button></div></div></section>
      <section className="task-panel" aria-label="当前任务"><div className="eyebrow">当前任务</div><h2>{step}</h2><ol className="task-steps"><li className={project?.status === "confirmed" ? "done" : "active"}><span>1</span><div><strong>描述需求</strong><small>{project?.status === "confirmed" ? "已整理项目内容" : "用对话说明产品、方向与数量"}</small></div></li><li className={run?.generation_mode === "preview" ? "done" : types.length ? "active" : ""}><span>2</span><div><strong>生成 3 篇预览</strong><small>先确认语气、结构和内容方向</small></div></li><li className={run?.generation_phase === "awaiting_preview_approval" ? "active" : run?.generation_phase === "completed" ? "done" : ""}><span>3</span><div><strong>确认方向</strong><small>满意后才批量生成剩余文案</small></div></li><li className={run?.generation_phase === "completed" ? "done" : ""}><span>4</span><div><strong>处理异常并输出</strong><small>只处理系统无法安全决定的内容</small></div></li></ol><div className="task-action">{run?.generation_phase === "awaiting_preview_approval" ? <><p><strong>3 篇预览已就绪。</strong> 认可方向后，会在同一批次生成剩余 {remaining} 篇。</p><button className="button button-primary button-large" disabled={busy} onClick={() => void confirmPreview()}>按此方向生成剩余 {remaining} 篇</button></> : run?.generation_phase === "completed" ? <><p>这一批文案已完成，可进入结果看板检查或输出。</p><Link className="button button-primary button-large" to={`/projects/${id}/board`}>查看本批文案</Link></> : <><p>{types.length ? `已设置 ${types.reduce((sum, type) => sum + type.quantity, 0)} 篇目标文案。` : "先通过对话整理内容方向与数量。"}</p><div className="inline-actions"><button className="button button-primary button-large" disabled={busy || !types.length} onClick={() => void start("preview")}>先生成 3 篇预览</button><button className="button button-text" disabled={busy || !types.length} onClick={() => void start("full")}>直接生成全部</button></div></>}</div><div className="task-facts"><span>帖子类型 <strong>{types.length}</strong></span><span>目标文案 <strong>{types.reduce((sum, type) => sum + type.quantity, 0)}</strong></span><span>当前批次 <strong>{run ? `第 ${run.batch_number} 批` : "未开始"}</strong></span></div></section>
    </div>
  </div>;
}
