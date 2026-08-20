import type { ConnectionStatus as ConnectionStatusType } from "../../api/contracts";
import { Icon } from "../../components/Icon";

export function ConnectionStatus({ value }: { value: ConnectionStatusType }) {
  const entries = [
    { label: "模型 API", configured: value.model.configured, simulated: value.model.adapter.toLowerCase().includes("fake"), adapter: value.model.adapter, detail: value.model.model },
    { label: "飞书电子表格", configured: value.feishu.configured, simulated: value.feishu.adapter.toLowerCase().includes("fake"), adapter: value.feishu.adapter, detail: value.feishu.target },
  ];
  return <section><div className="section-heading"><div><h2>连接状态</h2><p className="page-description">配置只从服务端环境变量读取，页面不会展示或保存凭证。</p></div></div><div className="connection-grid">{entries.map((entry) => <article className="surface-card connection-card" key={entry.label}><div className={`connection-symbol ${entry.configured ? "configured" : ""}`}><Icon name={entry.configured ? "check" : "warning"} /></div><div><h3>{entry.label}</h3><span className={`status-chip ${entry.simulated ? "warning" : entry.configured ? "success" : "warning"}`}>{entry.simulated ? "模拟连接" : entry.configured ? "已配置" : "未配置"}</span><p>{entry.adapter}</p><small>{entry.detail}</small></div></article>)}</div></section>;
}
