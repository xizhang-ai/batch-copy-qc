import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

export function EmptyState({ icon = "file", title, description, action }: { icon?: IconName; title: string; description: string; action?: ReactNode }) {
  return <div className="empty-state"><div><div className="empty-state-icon"><Icon name={icon} /></div><h2>{title}</h2><p>{description}</p>{action}</div></div>;
}
