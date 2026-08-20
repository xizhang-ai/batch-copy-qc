import { useState } from "react";
import type { CopyType, QcRule, RuleLevel } from "../../api/contracts";
import { api } from "../../api/service";

export function RuleEditor({ projectId, types, level, onCreated, onCancel }: { projectId: string; types: CopyType[]; level: RuleLevel; onCreated: (rule: QcRule) => void; onCancel: () => void }) {
  const [scope, setScope] = useState<"project" | "type">("project");
  const [typeId, setTypeId] = useState(types[0]?.id ?? "");
  const [statement, setStatement] = useState("");
  const [category, setCategory] = useState<QcRule["category"]>("other");
  const submit = async (event: React.FormEvent) => { event.preventDefault(); const result = await api.createRule(projectId, { scope, level, category, statement, copy_type_id: scope === "type" ? typeId : undefined, source_kind: scope === "type" ? "explicit_type_qc" : "explicit_project_qc", source_evidence: "人工新增", enabled: true }); onCreated(result); };
  return <form className="surface-card rule-create" onSubmit={submit}>
    <h3>新增{level === "hard" ? "硬规则" : level === "soft" ? "软规则" : "待确认规则"}</h3>
    <div className="field"><label>规则内容</label><textarea autoFocus className="textarea" value={statement} onChange={(event) => setStatement(event.target.value)} placeholder="用可判断的一句话描述" /></div>
    <div className="form-grid"><div className="field"><label>范围</label><select className="select" value={scope} onChange={(event) => setScope(event.target.value as "project" | "type")}><option value="project">项目全局</option><option value="type">单个帖子类型</option></select></div><div className="field"><label>类别</label><select className="select" value={category} onChange={(event) => setCategory(event.target.value as QcRule["category"])}><option value="claim">禁止宣称</option><option value="fact">事实依据</option><option value="style">表达风格</option><option value="structure">结构要求</option><option value="similarity">防照搬</option><option value="other">其他</option></select></div></div>
    {scope === "type" && <div className="field"><label>帖子类型</label><select className="select" required value={typeId} onChange={(event) => setTypeId(event.target.value)}><option value="">请选择</option>{types.map((type) => <option value={type.id} key={type.id}>{type.name || "未命名类型"}</option>)}</select></div>}
    <div className="inline-actions"><button className="button button-primary" disabled={!statement.trim() || (scope === "type" && !typeId)}>保存规则</button><button type="button" className="button button-text" onClick={onCancel}>取消</button></div>
  </form>;
}
