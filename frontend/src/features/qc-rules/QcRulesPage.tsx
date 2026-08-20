import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { CopyType, QcRule, RuleLevel } from "../../api/contracts";
import { api } from "../../api/service";
import { EmptyState } from "../../components/EmptyState";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Icon } from "../../components/Icon";
import { Skeleton } from "../../components/Skeleton";
import { RuleEditor } from "./RuleEditor";

const levelInfo: Record<RuleLevel, { title: string; description: string }> = {
  hard: { title: "硬规则", description: "违反时阻断完成，项目硬规则不可被类型覆盖。" },
  soft: { title: "软规则", description: "用于表达优化，类型规则可覆盖并保留来源。" },
  pending: { title: "待确认", description: "信息不足或存在冲突，确认前阻断生成。" },
};

export function QcRulesPage() {
  const { id = "" } = useParams();
  const [rules, setRules] = useState<QcRule[]>([]);
  const [types, setTypes] = useState<CopyType[]>([]);
  const [scopeFilter, setScopeFilter] = useState("all");
  const [adding, setAdding] = useState<RuleLevel>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = () => { setLoading(true); Promise.all([api.listRules(id), api.listCopyTypes(id)]).then(([nextRules, nextTypes]) => { setRules(nextRules); setTypes(nextTypes); }).catch((err: Error) => setError(err.message)).finally(() => setLoading(false)); };
  useEffect(load, [id]);
  const visibleRules = useMemo(() => rules.filter((rule) => scopeFilter === "all" || (scopeFilter === "project" ? rule.scope === "project" : rule.copy_type_id === scopeFilter)), [rules, scopeFilter]);
  const blockers = rules.filter((rule) => rule.enabled && (rule.level === "pending" || Boolean(rule.conflict)));
  const total = types.reduce((sum, type) => sum + type.quantity, 0);
  const canGenerate = types.length > 0 && total > 0 && blockers.length === 0 && types.every((type) => !type.input_modes.includes("reference_examples") || type.reference_profile?.confirmed);
  const saveRule = async (rule: QcRule) => { const saved = await api.saveRule(rule); setRules(rules.map((item) => item.id === saved.id ? saved : item)); };
  return <div className="page">
    <div className="page-header"><div><h1>QC 要求</h1><p className="page-description">项目全局规则与单个帖子类型规则会在生成批次中冻结快照，便于逐条追溯。</p></div><div className="header-actions"><label className="field"><span className="field-label">规则范围</span><select className="select" value={scopeFilter} onChange={(event) => setScopeFilter(event.target.value)}><option value="all">全部范围</option><option value="project">项目全局</option>{types.map((type) => <option value={type.id} key={type.id}>{type.name}</option>)}</select></label></div></div>
    {error && <ErrorNotice message={error} onRetry={load} />}
    {loading ? <div className="panel section-panel"><Skeleton lines={9} /></div> : <>
      <div className="qc-columns">{(["hard", "soft", "pending"] as RuleLevel[]).map((level) => <section className={`qc-rule-column ${level}`} key={level} aria-labelledby={`qc-${level}`}><div className="column-heading"><div><h2 id={`qc-${level}`}>{levelInfo[level].title}<span className="count-badge">{visibleRules.filter((rule) => rule.level === level).length}</span></h2><p>{levelInfo[level].description}</p></div><button className="button button-small button-secondary icon-button" aria-label={`新增${levelInfo[level].title}`} onClick={() => setAdding(level)}><Icon name="plus" /></button></div>
        {adding === level && <RuleEditor projectId={id} types={types} level={level} onCreated={(rule) => { setRules([...rules, rule]); setAdding(undefined); }} onCancel={() => setAdding(undefined)} />}
        <div className="rule-list">{visibleRules.filter((rule) => rule.level === level).map((rule) => <article className="surface-card rule-card" key={rule.id}>
          <div className="rule-top"><span className="source-chip">{rule.scope === "project" ? "项目全局" : types.find((type) => type.id === rule.copy_type_id)?.name || "帖子类型"}</span><label className="toggle"><input type="checkbox" checked={rule.enabled} onChange={(event) => saveRule({ ...rule, enabled: event.target.checked })} /><span aria-hidden="true" /></label></div>
          <textarea className="textarea compact" aria-label="规则内容" value={rule.statement} onChange={(event) => setRules(rules.map((item) => item.id === rule.id ? { ...item, statement: event.target.value } : item))} onBlur={() => saveRule(rules.find((item) => item.id === rule.id)!)} />
          <p className="rule-source">{rule.source_kind === "derived_type_constraint" ? "来自帖子类型约束 · 默认 QC" : rule.source_evidence}</p>
          {rule.conflict && <div className="notice danger"><Icon name="warning" />{rule.conflict}</div>}
          <div className="inline-actions"><button className="button button-small button-text" onClick={() => saveRule(rule)}><Icon name="edit" />保存</button><button className="button button-small button-text" aria-label="删除规则" onClick={async () => { await api.deleteRule(rule.id); setRules(rules.filter((item) => item.id !== rule.id)); }}><Icon name="trash" />删除</button></div>
        </article>)}{visibleRules.filter((rule) => rule.level === level).length === 0 && <EmptyState title={`暂无${levelInfo[level].title}`} description="需要时手动添加，不会自动补写未提供的边界。" />}</div>
      </section>)}</div>
      <section className="generation-summary panel section-panel"><div><div className="eyebrow">生成前校验摘要</div><h2>{canGenerate ? "准备就绪" : `${blockers.length || 1} 项阻断待处理`}</h2><p className="page-description">{types.length} 个帖子类型 · 计划生成 <strong>{total}</strong> 篇 · {rules.filter((rule) => rule.enabled).length} 条启用规则</p></div><div className="header-actions">{!canGenerate && <span className="status-chip warning"><Icon name="warning" />{blockers[0]?.statement || "请补齐并确认帖子类型"}</span>}<Link aria-disabled={!canGenerate} className={`button button-primary button-large${!canGenerate ? " disabled-link" : ""}`} to={canGenerate ? `/projects/${id}/board?start=confirm` : "#"}>开始生成<Icon name="arrow" /></Link></div></section>
    </>}
  </div>;
}
