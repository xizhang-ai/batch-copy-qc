import type { SVGProps } from "react";

export type IconName = "projects" | "types" | "qc" | "board" | "export" | "plus" | "arrow" | "close" | "retry" | "edit" | "trash" | "spark" | "check" | "warning" | "file" | "settings";

const paths: Record<IconName, React.ReactNode> = {
  projects: <><path d="M3.5 5.5h6l2 2h9v11h-17z"/><path d="M3.5 9.5h17"/></>,
  types: <><rect x="4" y="4" width="7" height="7" rx="2"/><rect x="13" y="4" width="7" height="7" rx="2"/><rect x="4" y="13" width="16" height="7" rx="2"/></>,
  qc: <><path d="M12 3l7 3v5c0 4.8-2.8 8-7 10-4.2-2-7-5.2-7-10V6z"/><path d="M9 12l2 2 4-5"/></>,
  board: <><rect x="3.5" y="4" width="5" height="16" rx="1.5"/><rect x="9.5" y="4" width="5" height="10" rx="1.5"/><rect x="15.5" y="4" width="5" height="13" rx="1.5"/></>,
  export: <><path d="M12 4v11"/><path d="M8 8l4-4 4 4"/><path d="M5 14v5h14v-5"/></>,
  plus: <><path d="M12 5v14M5 12h14"/></>, arrow: <><path d="M5 12h14M14 7l5 5-5 5"/></>, close: <path d="M6 6l12 12M18 6L6 18"/>,
  retry: <><path d="M19 7v5h-5"/><path d="M18 12a7 7 0 10-1.6 4.4"/></>, edit: <><path d="M4 20l4.5-1 9.8-9.8-3.5-3.5L5 15.5z"/><path d="M13.8 6.8l3.5 3.5"/></>, trash: <><path d="M5 7h14M9 7V4h6v3M7 7l1 13h8l1-13"/></>,
  spark: <><path d="M12 3l1.4 4.6L18 9l-4.6 1.4L12 15l-1.4-4.6L6 9l4.6-1.4z"/><path d="M18.5 15l.7 2.3 2.3.7-2.3.7-.7 2.3-.7-2.3-2.3-.7 2.3-.7z"/></>,
  check: <path d="M5 12l4 4L19 6"/>, warning: <><path d="M12 3l10 18H2z"/><path d="M12 9v5M12 18h.01"/></>, file: <><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 12h6M9 16h6"/></>, settings: <><circle cx="12" cy="12" r="3"/><path d="M19 12l2-1-2-4-2 .5-1.5-1.5.5-2-4-2-1 2-2 .5L7 3l-4 2 1 2-1 2-2 1 1 4 2-.5L5.5 15 5 17l4 2 1-2h2l1 2 4-2-.5-2 1.5-1.5z"/></>,
};

export function Icon({ name, ...props }: { name: IconName } & SVGProps<SVGSVGElement>) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name]}</svg>;
}
