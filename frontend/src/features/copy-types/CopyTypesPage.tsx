import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { ClassifiedTypeFile, CopyType } from "../../api/contracts";
import { api } from "../../api/service";
import { EmptyState } from "../../components/EmptyState";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Icon } from "../../components/Icon";
import { Skeleton } from "../../components/Skeleton";
import { CopyTypeEditor } from "./CopyTypeEditor";

export function CopyTypesPage() {
  const { id = "" } = useParams();
  const [types, setTypes] = useState<CopyType[]>([]);
  const [files, setFiles] = useState<ClassifiedTypeFile[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const classifyInputRef = useRef<HTMLInputElement>(null);
  const load = async () => { setLoading(true); try { const nextTypes = await api.listCopyTypes(id); const nextFiles = await api.listClassifiedFiles(id); setTypes(nextTypes); setFiles(nextFiles); setSelectedId((current) => current || nextTypes[0]?.id || ""); } catch (err) { setError((err as Error).message); } finally { setLoading(false); } };
  useEffect(() => { void load(); }, [id]);
  const add = async () => { const created = await api.createCopyType(id); setTypes([...types, created]); setSelectedId(created.id); };
  const selected = types.find((item) => item.id === selectedId);
  return <div className="page">
    <div className="page-header"><div><h1>帖子类型</h1><p className="page-description">不预设任何种草类型。用参考案例、描述要求或两者组合，建立自己的生成依据。</p></div><div className="header-actions"><button className="button button-secondary" onClick={() => classifyInputRef.current?.click()}><Icon name="file" />上传未分类文件</button><input ref={classifyInputRef} hidden multiple type="file" accept=".txt,.md,.docx" onChange={async (event) => { const selected = Array.from(event.target.files ?? []); if (selected.length) setFiles([...files, ...await api.classifyTypeFiles(id, selected)]); }} /><button className="button button-primary button-large" onClick={add}><Icon name="plus" />添加帖子类型</button><Link className="button button-secondary" to={`/projects/${id}/qc`}>下一步：QC 要求<Icon name="arrow" /></Link></div></div>
    {error && <ErrorNotice message={error} onRetry={load} />}
    {loading ? <div className="panel section-panel"><Skeleton lines={8} /></div> : types.length === 0 ? <div className="panel"><EmptyState icon="types" title="还没有帖子类型" description="点击“添加帖子类型”建立空白类型。这里不会出现系统推荐或内置模板。" action={<button className="button button-primary" onClick={add}><Icon name="plus" />添加帖子类型</button>} /></div> : <div className="types-workspace">
      <aside className="types-list panel" aria-label="帖子类型列表">{types.map((type) => <button className={`type-list-item${selectedId === type.id ? " active" : ""}`} onClick={() => setSelectedId(type.id)} key={type.id}><span><strong>{type.name || "未命名帖子类型"}</strong><small>{type.quantity} 篇 · {type.sources.map((source) => ({ manual: "手动", brief: "Brief", reference: "爆款参考" }[source])).join(" / ")}</small></span><Icon name="arrow" /></button>)}
        {files.length > 0 && <div className="unclassified-files"><h3>未分类文件</h3>{files.map((file) => <div className="file-suggestion" key={file.id}><strong>{file.filename}</strong><p>{file.evidence}</p><span className="status-chip warning">建议：{file.suggested_type} · {file.confidence === "high" ? "高" : "中"}置信</span><select className="select" aria-label={`${file.filename}归属`} value={file.assigned_type_id ?? ""} onChange={async (event) => { const copyTypeId = event.target.value || null; try { await api.assignTypeFile(file.id, copyTypeId); setFiles(files.map((item) => item.id === file.id ? { ...item, assigned_type_id: copyTypeId } : item)); } catch (err) { setError((err as Error).message); } }}><option value="">未归属</option>{types.map((type) => <option key={type.id} value={type.id}>{type.name || "未命名类型"}</option>)}</select></div>)}</div>}
      </aside>
      {selected && <CopyTypeEditor key={selected.id} initial={selected} onSaved={(saved) => setTypes(types.map((item) => item.id === saved.id ? saved : item))} onDelete={async () => { await api.deleteCopyType(selected.id); const next = types.filter((item) => item.id !== selected.id); setTypes(next); setSelectedId(next[0]?.id ?? ""); }} />}
    </div>}
  </div>;
}
