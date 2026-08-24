import { Navigate, Route, Routes } from "react-router-dom";
import { BoardPage } from "../features/board/BoardPage";
import { CopyTypesPage } from "../features/copy-types/CopyTypesPage";
import { ExportPage } from "../features/export/ExportPage";
import { ProjectContentPage } from "../features/project-content/ProjectContentPage";
import { NewProjectPage } from "../features/projects/NewProjectPage";
import { ProjectListPage } from "../features/projects/ProjectListPage";
import { ProjectWorkspacePage } from "../features/workspace/ProjectWorkspacePage";
import { QcRulesPage } from "../features/qc-rules/QcRulesPage";
import { AppShell } from "../features/shell/AppShell";
import { NotFoundPage } from "./NotFoundPage";

export function AppRouter() {
  return <Routes>
    <Route element={<AppShell />}>
      <Route index element={<Navigate to="/projects" replace />} />
      <Route path="projects" element={<ProjectListPage />} />
      <Route path="projects/new" element={<NewProjectPage />} />
      <Route path="projects/:id" element={<ProjectWorkspacePage />} />
      <Route path="projects/:id/content" element={<ProjectContentPage />} />
      <Route path="projects/:id/types" element={<CopyTypesPage />} />
      <Route path="projects/:id/qc" element={<QcRulesPage />} />
      <Route path="projects/:id/board" element={<BoardPage />} />
      <Route path="projects/:id/export" element={<ExportPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Route>
  </Routes>;
}
