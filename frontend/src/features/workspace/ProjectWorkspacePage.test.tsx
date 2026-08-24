import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, vi } from "vitest";
import { ProjectWorkspacePage } from "./ProjectWorkspacePage";
import { resetMockApi } from "../../api/mockService";
import { api } from "../../api/service";

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
