import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { Project } from "../../api/contracts";
import { api } from "../../api/service";
import { EmptyState } from "../../components/EmptyState";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Icon } from "../../components/Icon";
import { Skeleton } from "../../components/Skeleton";

export function ProjectListPage() {
  const [items, setItems] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = () => { setLoading(true); setError(""); api.listProjects().then(setItems).catch((err: Error) => setError(err.message)).finally(() => setLoading(false)); };
  useEffect(load, []);
  return <div className="page">
    <div className="page-header"><div><h1>项目</h1><p className="page-description">每个项目独立保存产品事实、帖子类型、QC 规则与输出记录。</p></div><Link className="button button-primary button-large" to="/projects/new"><Icon name="plus" />新建项目</Link></div>
    {error && <ErrorNotice message={error} onRetry={load} />}
    {loading ? <div className="panel section-panel"><Skeleton lines={5} /></div> : items.length === 0 ? <div className="panel"><EmptyState icon="projects" title="还没有项目" description="新建项目并上传 Brief，AI 会先拆解内容供你确认。" action={<Link className="button button-primary" to="/projects/new">新建项目并上传 Brief</Link>} /></div> :
      <div className="cards-grid">{items.map((project) => <article className="surface-card project-card" key={project.id}>
        <div className="chip-row"><span className={`status-chip ${project.status === "confirmed" ? "success" : "warning"}`}>{project.status === "confirmed" ? "项目内容已确认" : "待完成配置"}</span></div>
        <h2 style={{ marginTop: 20 }}>{project.name}</h2>
        <p className="page-description">{project.brand || "品牌未填写"} · {project.category || "品类未填写"}</p>
        <div className="card-footer"><span className="meta">更新于 {new Date(project.updated_at).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span><Link className="button button-secondary" to={`/projects/${project.id}/content`}>进入项目<Icon name="arrow" /></Link></div>
      </article>)}</div>}
  </div>;
}
