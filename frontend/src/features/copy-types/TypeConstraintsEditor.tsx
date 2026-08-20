import type { CopyType } from "../../api/contracts";

const fields: Array<[keyof CopyType["requirements"], string, string]> = [
  ["title_direction", "标题方向", "例如：具体场景开头，克制而不夸张"],
  ["body_structure", "正文结构", "例如：痛点 → 使用 → 体验 → 事实 → 适用人群"],
  ["tone", "语气", "例如：像朋友聊天，少感叹号"],
  ["persona", "人设", "例如：规律通勤的普通上班族"],
  ["scenario", "场景", "例如：午后三点工位"],
  ["topic_requirements", "话题要求", "例如：3–5 个精准话题"],
];

function LinesField({ label, value, onChange, placeholder }: { label: string; value: string[]; onChange: (value: string[]) => void; placeholder: string }) {
  return <div className="field"><label>{label}</label><textarea className="textarea" value={value.join("\n")} onChange={(event) => onChange(event.target.value.split("\n").map((line) => line.trim()).filter(Boolean))} placeholder={placeholder} /><span className="meta">每行一条；未单独填写类型 QC 时会自动生成可编辑的默认 QC。</span></div>;
}

export function TypeConstraintsEditor({ value, onChange }: { value: CopyType; onChange: (value: CopyType) => void }) {
  return <div className="form-stack">
    <div className="form-grid">{fields.map(([key, label, placeholder]) => <div className="field" key={key}><label htmlFor={`requirement-${key}`}>{label}</label><textarea id={`requirement-${key}`} className="textarea" value={value.requirements[key]} onChange={(event) => onChange({ ...value, requirements: { ...value.requirements, [key]: event.target.value } })} placeholder={placeholder} /></div>)}</div>
    <div className="form-grid"><LinesField label="一定要有" value={value.must_include} onChange={(must_include) => onChange({ ...value, must_include })} placeholder="青柚味\n330ml\n配料事实" /><LinesField label="一定不要有" value={value.must_avoid} onChange={(must_avoid) => onChange({ ...value, must_avoid })} placeholder="减肥\n燃脂\n全网最好喝" /></div>
  </div>;
}
