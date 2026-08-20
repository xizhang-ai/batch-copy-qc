import { useRef, useState } from "react";
import type { CopyType, ReferenceExample } from "../../api/contracts";
import { Icon } from "../../components/Icon";

function newExample(): ReferenceExample { return { id: crypto.randomUUID(), title: "", body: "", topics: [], raw_text: "" }; }

export function ReferenceExamplesEditor({ value, analyzing, onChange, onAnalyze }: { value: CopyType; analyzing: boolean; onChange: (value: CopyType) => void; onAnalyze: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [fileError, setFileError] = useState("");
  const update = (id: string, patch: Partial<ReferenceExample>) => onChange({ ...value, references: value.references.map((item) => item.id === id ? { ...item, ...patch } : item) });
  const add = () => value.references.length < 5 && onChange({ ...value, references: [...value.references, newExample()] });
  const loadTextFile = async (file?: File) => {
    if (!file) return;
    if (file.name.toLowerCase().endsWith(".docx")) { setFileError("参考案例暂不在浏览器内解析 docx。请将其上传到“类型 Brief”，或转为 txt/md 后再添加。"); return; }
    setFileError("");
    const text = await file.text(); const example = newExample(); example.raw_text = text; example.body = text; onChange({ ...value, references: [...value.references, example].slice(0, 5) });
  };
  const profile = value.reference_profile;
  return <div className="reference-layout">
    <div className="form-stack">
      <div className="notice"><strong>原帖全文与确认后的画像都会进入生成 Prompt。</strong><br />来源事实不会带入当前项目；生成稿会执行防照搬相似度 QC。</div>
      {value.references.map((example, index) => <article className="surface-card reference-card" key={example.id}>
        <div className="page-header" style={{ marginBottom: 12 }}><div><h3>参考案例 {index + 1}</h3><span className="meta">完整保留标题、正文、话题与原文</span></div><button className="button button-small button-text" aria-label={`删除参考案例${index + 1}`} onClick={() => onChange({ ...value, references: value.references.filter((item) => item.id !== example.id), reference_profile: undefined })}><Icon name="trash" />删除</button></div>
        <div className="field"><label htmlFor={`${example.id}-title`}>标题</label><input id={`${example.id}-title`} className="input" value={example.title} onChange={(event) => update(example.id, { title: event.target.value })} /></div>
        <div className="field"><label htmlFor={`${example.id}-body`}>正文</label><textarea id={`${example.id}-body`} className="textarea" value={example.body} onChange={(event) => update(example.id, { body: event.target.value, raw_text: `${example.title}\n${event.target.value}\n${example.topics.map((topic) => `#${topic}`).join(" ")}` })} /></div>
        <div className="field"><label htmlFor={`${example.id}-topics`}>话题</label><input id={`${example.id}-topics`} className="input" value={example.topics.join("、")} onChange={(event) => update(example.id, { topics: event.target.value.split(/[、,#\s]+/).filter(Boolean) })} placeholder="办公室饮品、打工人日常" /></div>
      </article>)}
      <div className="inline-actions"><button className="button button-secondary" disabled={value.references.length >= 5} onClick={add}><Icon name="plus" />添加案例</button><button className="button button-secondary" disabled={value.references.length >= 5} onClick={() => fileRef.current?.click()}><Icon name="file" />上传 txt/md/docx</button><input ref={fileRef} hidden type="file" accept=".txt,.md,.docx" onChange={(event) => loadTextFile(event.target.files?.[0])} /><span className="meta">{value.references.length}/5 篇；一篇即可分析</span></div>{fileError && <div className="notice warning" role="alert">{fileError}</div>}
      <button className="button button-primary" disabled={analyzing || !value.references.some((item) => item.body.trim())} onClick={onAnalyze}><Icon name="spark" />{analyzing ? "正在分析风格…" : profile ? "重新分析风格" : "分析并生成风格画像"}</button>
    </div>
    <aside className="profile-panel panel section-panel">
      <h2>可编辑风格画像</h2>
      {!profile ? <p className="page-description">录入至少一篇完整参考帖后分析。系统只学习表达方式，不继承来源事实。</p> : <div className="form-stack">
        {([
          ["title_hook", "标题钩子"], ["structure_rhythm", "结构节拍"], ["point_of_view", "叙事视角"], ["tone", "语气"], ["persona", "人设"], ["scenario", "场景"], ["information_density", "信息密度"], ["ending", "结尾"], ["topic_strategy", "标签策略"],
        ] as const).map(([key, label]) => <div className="field" key={key}><label>{label}</label><textarea className="textarea compact" value={profile[key]} onChange={(event) => onChange({ ...value, reference_profile: { ...profile, [key]: event.target.value } })} /></div>)}
        <div className="field"><label>来源事实（不会带入当前项目）</label><textarea className="textarea" value={profile.source_facts.join("\n")} onChange={(event) => onChange({ ...value, reference_profile: { ...profile, source_facts: event.target.value.split("\n").filter(Boolean) } })} /></div>
        <div className="field"><label>避免照搬的独特表达</label><textarea className="textarea" value={profile.avoid_expressions.join("\n")} onChange={(event) => onChange({ ...value, reference_profile: { ...profile, avoid_expressions: event.target.value.split("\n").filter(Boolean) } })} /></div>
        <label className="check-row"><input type="checkbox" checked={profile.confirmed} onChange={(event) => onChange({ ...value, reference_profile: { ...profile, confirmed: event.target.checked } })} /><span><strong>确认风格画像</strong><br /><small>确认后才允许使用该类型生成。</small></span></label>
      </div>}
    </aside>
  </div>;
}
