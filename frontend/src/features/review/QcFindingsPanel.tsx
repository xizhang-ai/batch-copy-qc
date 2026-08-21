import type { QcFinding } from "../../api/contracts";
import { Icon } from "../../components/Icon";

export function QcFindingsPanel({ findings, onLocate }: { findings: QcFinding[]; onLocate: (finding: QcFinding) => void }) {
  const legacyTagMessage = "Tags must start with # and contain no spaces";
  const normalized = findings.map((finding) => finding.message === legacyTagMessage ? {
    ...finding,
    message: "话题标签格式需要检查",
    suggestion: "标签文字中不要留空格；无需手动输入 #，界面会自动补充。",
  } : finding);
  const grouped = Array.from(normalized.reduce((groups, finding) => {
    const key = `${finding.level}|${finding.category}|${finding.message}`;
    const existing = groups.get(key);
    if (!existing) groups.set(key, { ...finding });
    else existing.evidence = Array.from(new Set([existing.evidence, finding.evidence].filter(Boolean))).join("、");
    return groups;
  }, new Map<string, QcFinding>()).values());
  const categoryLabel = (category: string) => ({ tags: "话题标签", claim: "宣称", fact: "事实", style: "风格", structure: "结构", similarity: "相似度" }[category] ?? category);
  const checkLabel = (finding: QcFinding) => Number.isFinite(finding.confidence)
    ? `置信 ${Math.round((finding.confidence ?? 0) * 100)}%`
    : finding.source === "model" ? "AI 检查" : finding.source === "system" ? "系统检查" : "格式检查";
  return <div className="form-stack"><div><h2>QC 结果</h2><p className="page-description">证据来自当前版本，不确定项不会自动放行。</p></div>{grouped.length === 0 ? <div className="notice"><Icon name="check" /> 当前没有未解决问题。</div> : grouped.map((finding) => <article className={`finding-card ${finding.level}`} key={finding.id}><div className="rule-top"><span className={`status-chip ${finding.level === "hard" ? "danger" : "warning"}`}>{finding.level === "hard" ? "硬规则" : "软规则"} · {categoryLabel(finding.category)}</span><span className="meta">{checkLabel(finding)}</span></div><h3>{finding.message}</h3>{finding.evidence && <blockquote>{finding.evidence}</blockquote>}{finding.suggestion && <p>{finding.suggestion}</p>}<button className="button button-small button-secondary" onClick={() => onLocate(finding)}>定位证据</button></article>)}</div>;
}
