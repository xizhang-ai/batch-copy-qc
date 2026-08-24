import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/service";
import { ErrorNotice } from "../../components/ErrorNotice";

export function NewProjectPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", brand: "", category: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: React.FormEvent) => { event.preventDefault(); setSaving(true); setError(""); try { const project = await api.createProject(form); navigate(`/projects/${project.id}`); } catch (err) { setError((err as Error).message); } finally { setSaving(false); } };
  return <div className="page"><div className="page-header"><div><h1>建立项目</h1><p className="page-description">先给项目一个清楚的名字。品牌和品类可以留空，稍后从 Brief 中补充。</p></div></div>
    {error && <ErrorNotice message={error} />}
    <form className="panel section-panel form-stack" style={{ maxWidth: 720 }} onSubmit={submit}>
      <div className="field"><label htmlFor="project-name">项目名称</label><input id="project-name" className="input" required autoFocus value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="例如：新品夏季种草项目" /></div>
      <div className="form-grid"><div className="field"><label htmlFor="brand">品牌</label><input id="brand" className="input" value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} /></div><div className="field"><label htmlFor="category">快消品类</label><input id="category" className="input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} /></div></div>
      <div className="inline-actions"><button className="button button-primary button-large" disabled={!form.name.trim() || saving}>{saving ? "正在建立…" : "建立并添加 Brief"}</button><button type="button" className="button button-text" onClick={() => navigate("/projects")}>取消</button></div>
    </form>
  </div>;
}
