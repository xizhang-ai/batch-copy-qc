import type { BriefFinding, BriefSection } from "../../api/contracts";
import { Icon } from "../../components/Icon";

const sectionLabels: Record<BriefSection, string> = { project_content: "项目内容", copy_requirements: "文案需求", qc_requirements: "QC 要求", needs_confirmation: "待确认" };
const confidenceLabels = { high: "高置信", medium: "中置信", low: "低置信" };

export function ParsedSectionEditor({ section, findings, onChange, onAdd }: { section: BriefSection; findings: BriefFinding[]; onChange: (current: BriefFinding, next: BriefFinding | null) => void; onAdd: (section: BriefSection) => void }) {
  return <section className="panel section-panel parsed-section"><div className="page-header" style={{ marginBottom: 12 }}><div><h2>{sectionLabels[section]}</h2><span className="meta">{findings.length} 项</span></div><button className="button button-small button-secondary" onClick={() => onAdd(section)}><Icon name="plus" />添加</button></div>
    <div className="form-stack">{findings.length === 0 ? <p className="meta">暂无内容，可按需要手动添加。</p> : findings.map((finding) => <div className="surface-card" style={{ padding: 16 }} key={finding.id}>
      <div className="form-grid"><div className="field"><label htmlFor={`${finding.id}-label`}>字段</label><input id={`${finding.id}-label`} className="input" value={finding.label} onChange={(event) => onChange(finding, { ...finding, label: event.target.value })} /></div><div className="field"><label htmlFor={`${finding.id}-section`}>分区</label><select id={`${finding.id}-section`} className="select" value={finding.section} onChange={(event) => onChange(finding, { ...finding, section: event.target.value as BriefSection })}>{Object.entries(sectionLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></div></div>
      <div className="field" style={{ marginTop: 12 }}><label htmlFor={`${finding.id}-value`}>确认值</label><textarea id={`${finding.id}-value`} className="textarea" value={finding.value} onChange={(event) => onChange(finding, { ...finding, value: event.target.value })} placeholder="保持空白，等待补充" /></div>
      <div className="notice" style={{ marginTop: 12 }}><strong>原文依据</strong><br />{finding.evidence || "无原文依据"}</div>
      <div className="card-footer" style={{ display: "flex", justifyContent: "space-between", marginTop: 12 }}><span className={`status-chip ${finding.confidence === "low" ? "warning" : ""}`}>{confidenceLabels[finding.confidence]}</span><button className="button button-small button-text" aria-label={`删除${finding.label}`} onClick={() => onChange(finding, null)}><Icon name="trash" />删除</button></div>
    </div>)}</div>
  </section>;
}
