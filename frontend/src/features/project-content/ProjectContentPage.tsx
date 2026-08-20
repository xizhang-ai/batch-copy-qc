import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { BriefFinding, BriefSection, ParsedBrief, Project } from "../../api/contracts";
import { api } from "../../api/service";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Icon } from "../../components/Icon";
import { Skeleton } from "../../components/Skeleton";
import { BriefInputPanel } from "./BriefInputPanel";
import { ParsedSectionEditor } from "./ParsedSectionEditor";

const sections: BriefSection[] = ["project_content", "copy_requirements", "qc_requirements", "needs_confirmation"];

function parsedFromProject(project: Project): ParsedBrief | undefined {
  const structured = project.structured as Record<string, unknown> | undefined;
  if (!structured) return undefined;
  if (Array.isArray(structured.findings)) return { source_name: "已保存项目内容", findings: structured.findings as BriefFinding[] };
  const findings = sections.flatMap((section) => {
    const raw = section === "needs_confirmation" ? structured.pending_confirmation : structured[section];
    if (Array.isArray(raw)) return raw as BriefFinding[];
    if (raw && typeof raw === "object" && Array.isArray((raw as { findings?: unknown[] }).findings)) return (raw as { findings: BriefFinding[] }).findings;
    return [];
  });
  return findings.length ? { source_name: "已保存项目内容", findings } : undefined;
}

export function ProjectContentPage() {
  const { id = "" } = useParams();
  const [project, setProject] = useState<Project>();
  const [parsed, setParsed] = useState<ParsedBrief>();
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { api.getProject(id).then((next) => { setProject(next); const restored = parsedFromProject(next); if (restored) setParsed(restored); }).catch((err: Error) => setError(err.message)); }, [id]);
  useEffect(() => { const handler = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault(); }; window.addEventListener("beforeunload", handler); return () => window.removeEventListener("beforeunload", handler); }, [dirty]);
  const parse = async (input: { text?: string; file?: File }) => { setBusy(true); setError(""); try { setParsed(await api.parseProjectBrief(id, input)); setDirty(true); } catch (err) { setError((err as Error).message); } finally { setBusy(false); } };
  const changeFinding = (current: BriefFinding, next: BriefFinding | null) => { if (!parsed) return; setParsed({ ...parsed, findings: next ? parsed.findings.map((item) => item.id === current.id ? next : item) : parsed.findings.filter((item) => item.id !== current.id) }); setDirty(true); };
  const addFinding = (section: BriefSection) => { if (!parsed) return; setParsed({ ...parsed, findings: [...parsed.findings, { id: crypto.randomUUID(), section, label: "", value: "", evidence: "人工补充", confidence: "high" }] }); setDirty(true); };
  const save = async () => { if (!parsed) return; setBusy(true); try { setProject(await api.saveProjectFindings(id, parsed)); setDirty(false); } catch (err) { setError((err as Error).message); } finally { setBusy(false); } };
  return <div className="page">
    <div className="page-header"><div>{project ? <><div className="eyebrow">{project.brand || "品牌待补充"} · {project.category || "品类待补充"}</div><h1>{project.name}</h1></> : <Skeleton lines={2} />}<p className="page-description">确认项目事实和边界后，才会进入帖子类型与生成流程。</p></div><div className="header-actions">{project?.status === "confirmed" && <span className="status-chip success"><Icon name="check" />内容已确认</span>}<Link className="button button-secondary" to={`/projects/${id}/types`}>下一步：帖子类型<Icon name="arrow" /></Link></div></div>
    {error && <ErrorNotice message={error} />}
    {!parsed && <BriefInputPanel busy={busy} onParse={parse} />}
    {busy && !parsed && <div className="panel section-panel" style={{ marginTop: 16 }}><Skeleton lines={8} /></div>}
    {parsed && <><div className="notice" style={{ marginBottom: 20 }}><strong>已从 {parsed.source_name} 拆出 {parsed.findings.length} 项。</strong> 每项都保留原文依据与置信度；请修改后明确保存。</div><div className="parsed-grid">{sections.map((section) => <ParsedSectionEditor key={section} section={section} findings={parsed.findings.filter((item) => item.section === section)} onChange={changeFinding} onAdd={addFinding} />)}</div><div className="sticky-save"><span>{dirty ? "有未保存修改" : "所有修改已保存"}</span><button className="button button-primary button-large" disabled={!dirty || busy} onClick={save}>{busy ? "正在保存…" : "保存并确认项目内容"}</button></div></>}
  </div>;
}
