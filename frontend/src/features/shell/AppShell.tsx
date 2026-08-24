import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Icon, type IconName } from "../../components/Icon";
import { api } from "../../api/service";

const navItems: Array<{ label: string; segment: string; icon: IconName }> = [
  { label: "工作台", segment: "", icon: "projects" },
  { label: "文案看板", segment: "board", icon: "board" },
  { label: "飞书输出", segment: "export", icon: "export" },
];

export function AppShell() {
  const location = useLocation();
  const projectId = location.pathname.match(/^\/projects\/([^/]+)/)?.[1];
  const pathFor = (segment: string) => projectId && projectId !== "new" ? (segment ? `/projects/${projectId}/${segment}` : `/projects/${projectId}`) : "/projects";

  return <div className="app-frame">
    <div className="app-shell">
      <aside className="icon-rail" aria-label="快捷导航">
        <NavLink to="/projects" className="brand-mark" aria-label="种草文案 QC 首页">种</NavLink>
        {navItems.map((item) => <NavLink key={item.segment} to={pathFor(item.segment)} className="rail-button" aria-label={item.label}><Icon name={item.icon} /></NavLink>)}
        <div className="rail-spacer" />
        <button className="rail-button" aria-label="应用设置"><Icon name="settings" /></button>
      </aside>
      <main className="app-main">
        <header className="top-area">
          <span />
          <nav className="top-nav" aria-label="项目流程">
            {navItems.map((item) => <NavLink end={!item.segment} key={item.segment || "workspace"} to={pathFor(item.segment)} className={({ isActive }) => `nav-link${isActive || (!projectId && !item.segment) ? " active" : ""}`}>{item.label}</NavLink>)}
          </nav>
          <span className="connection-dot">{api.mode === "mock" ? "演示数据" : "API 已连接"}</span>
        </header>
        <Outlet />
      </main>
    </div>
  </div>;
}
