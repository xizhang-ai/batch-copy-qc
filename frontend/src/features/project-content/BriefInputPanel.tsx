import { useRef, useState } from "react";
import { Icon } from "../../components/Icon";

export function BriefInputPanel({ busy, onParse }: { busy: boolean; onParse: (input: { text?: string; file?: File }) => void }) {
  const [mode, setMode] = useState<"text" | "file">("text");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File>();
  const [fileError, setFileError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const selectFile = (selected?: File) => {
    if (!selected) return;
    const ext = selected.name.split(".").pop()?.toLowerCase();
    if (!ext || !["txt", "md", "docx"].includes(ext)) { setFileError("只支持 txt、md、docx 文件"); return; }
    setFileError(""); setFile(selected);
  };
  return <section className="panel section-panel"><div className="page-header" style={{ marginBottom: 16 }}><div><h2>上传项目 Brief</h2><p className="page-description">上传一段完整材料即可，AI 会拆成项目内容、文案需求和 QC 要求。</p></div><div className="chip-row" role="tablist" aria-label="Brief 输入方式"><button type="button" className={`button button-small ${mode === "text" ? "button-primary" : "button-secondary"}`} onClick={() => setMode("text")}>粘贴文字</button><button type="button" className={`button button-small ${mode === "file" ? "button-primary" : "button-secondary"}`} onClick={() => setMode("file")}>上传文件</button></div></div>
    {mode === "text" ? <div className="field"><label htmlFor="brief-text">Brief 原文</label><textarea id="brief-text" className="textarea" style={{ minHeight: 200 }} value={text} onChange={(event) => setText(event.target.value)} placeholder="粘贴项目名称、品牌、SKU、人群、场景、卖点事实、依据、活动信息和禁止宣称等材料…" /></div> :
      <div className="field"><span className="field-label">Brief 文件</span><button type="button" className="check-row" style={{ width: "100%", minHeight: 120, justifyContent: "center", alignItems: "center" }} onClick={() => inputRef.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); selectFile(event.dataTransfer.files[0]); }}><Icon name="file" />{file ? file.name : "拖入文件或点击选择"}</button><input ref={inputRef} hidden type="file" accept=".txt,.md,.docx" onChange={(event) => selectFile(event.target.files?.[0])} /><span className="meta">支持 txt、md、docx，建议小于 10MB</span>{fileError && <span role="alert" style={{ color: "var(--danger)" }}>{fileError}</span>}</div>}
    <div className="inline-actions" style={{ marginTop: 16 }}><button className="button button-primary" disabled={busy || (mode === "text" ? !text.trim() : !file)} onClick={() => onParse(mode === "text" ? { text } : { file })}><Icon name="spark" />{busy ? "正在识别和分类…" : "AI 拆解 Brief"}</button><span className="meta">缺失内容会留空，不会自动编造。</span></div>
  </section>;
}
