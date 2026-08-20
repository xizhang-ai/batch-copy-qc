import type { QcFinding } from "../../api/contracts";
import { Icon } from "../../components/Icon";

export function QcFindingsPanel({ findings, onLocate }: { findings: QcFinding[]; onLocate: (finding: QcFinding) => void }) {
  return <div className="form-stack"><div><h2>QC 结果</h2><p className="page-description">证据来自当前版本，不确定项不会自动放行。</p></div>{findings.length === 0 ? <div className="notice"><Icon name="check" /> 当前没有未解决问题。</div> : findings.map((finding) => <article className={`finding-card ${finding.level}`} key={finding.id}><div className="rule-top"><span className={`status-chip ${finding.level === "hard" ? "danger" : "warning"}`}>{finding.level === "hard" ? "硬规则" : "软规则"} · {finding.category}</span><span className="meta">置信 {Math.round(finding.confidence * 100)}%</span></div><h3>{finding.message}</h3><blockquote>{finding.evidence}</blockquote><p>{finding.suggestion}</p><button className="button button-small button-secondary" onClick={() => onLocate(finding)}>定位证据</button></article>)}</div>;
}
