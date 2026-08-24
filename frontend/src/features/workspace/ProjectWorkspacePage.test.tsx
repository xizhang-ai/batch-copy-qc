import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, vi } from "vitest";
import { ProjectWorkspacePage } from "./ProjectWorkspacePage";
import { resetMockApi } from "../../api/mockService";
import { api } from "../../api/service";
import { ApiError } from "../../api/client";

function renderWorkspace() {
  return render(<MemoryRouter initialEntries={["/projects/p-demo"]}><Routes><Route path="/projects/:id" element={<ProjectWorkspacePage />} /></Routes></MemoryRouter>);
}

beforeEach(() => { cleanup(); resetMockApi(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("turns a message into an explicit task proposal", async () => {
  const user = userEvent.setup();
  renderWorkspace();
  const composer = await screen.findByRole("textbox", { name: "告诉我你想做什么" });
  await user.type(composer, "给新品做 20 篇通勤种草");
  await user.click(screen.getByRole("button", { name: "发送" }));
  expect(await screen.findByText("我准备这样做")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "应用到任务" }));
  expect(await screen.findByText("已更新任务配置。")).toBeInTheDocument();
});

it("starts a three-copy preview before offering continuation", async () => {
  const user = userEvent.setup();
  const createRun = vi.spyOn(api, "createGenerationRun");
  renderWorkspace();
  const preview = await screen.findByRole("button", { name: "先生成 3 篇预览" });
  await waitFor(() => expect(preview).toBeEnabled());
  await user.click(preview);
  expect(createRun).toHaveBeenCalledWith("p-demo", "preview");
  expect(await screen.findByText("3 篇预览已就绪。", { exact: false })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "按此方向生成剩余 1 篇" })).toBeInTheDocument();
});

it("keeps Brief upload and the complete editor accessible from the workspace", async () => {
  const user = userEvent.setup();
  renderWorkspace();
  await user.click(screen.getByRole("button", { name: "上传 Brief" }));
  expect(await screen.findByRole("heading", { name: "上传项目 Brief" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "完整 Brief 编辑" })).toHaveAttribute("href", "/projects/p-demo/content");
});

it("explains which post type is blocking generation without asking for the project Brief again", async () => {
  const user = userEvent.setup();
  vi.spyOn(api, "createGenerationRun").mockRejectedValue(new ApiError("GENERATION_VALIDATION_FAILED", "Generation prerequisites are not met", 400, [
    { code: "COPY_TYPE_INPUT_REQUIRED", resource_id: "ct-commute" },
  ]));
  renderWorkspace();
  const preview = await screen.findByRole("button", { name: "先生成 3 篇预览" });
  await waitFor(() => expect(preview).toBeEnabled());

  await user.click(preview);

  expect(await screen.findByText(/通勤包里常备.*还没有自己的内容依据/)).toBeInTheDocument();
  expect(screen.getByText(/无需重新上传项目 Brief/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "补充帖子类型" })).toHaveAttribute("href", "/projects/p-demo/types?type=ct-commute");
});

it("shows failed historical batches as exceptions instead of pretending they are generating", async () => {
  vi.spyOn(api, "listGenerationRuns").mockResolvedValue([{ id: "failed-run", project_id: "p-demo", status: "partial_failed", total_requested: 4, batch_number: 9, label: "第 9 批", archived: false, created_at: "2026-08-25T00:00:00Z", generation_mode: "full", generation_phase: "completed" }]);
  renderWorkspace();

  expect(await screen.findByRole("heading", { name: "处理生成异常" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "查看本批异常" })).toHaveAttribute("href", "/projects/p-demo/board?run=failed-run");
});
