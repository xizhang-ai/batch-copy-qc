import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ProjectContentPage } from "./ProjectContentPage";

it("parses one brief into four editable sections and restores them after refresh", async () => {
  const user = userEvent.setup();
  const view = render(<MemoryRouter initialEntries={["/projects/p-demo/content"]}><Routes><Route path="/projects/:id/content" element={<ProjectContentPage />} /></Routes></MemoryRouter>);
  const input = await screen.findByLabelText("Brief 原文");
  await user.type(input, "品牌微沫，青柚气泡水，禁止减肥宣称。");
  await user.click(screen.getByRole("button", { name: /AI 拆解 Brief/ }));
  expect(await screen.findByRole("heading", { name: "项目内容" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "文案需求" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "QC 要求" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "待确认" })).toBeInTheDocument();
  expect(screen.getAllByText("原文依据").length).toBeGreaterThan(0);
  await user.click(screen.getByRole("button", { name: "保存并确认项目内容" }));
  expect(await screen.findByText("所有修改已保存")).toBeInTheDocument();

  view.unmount();
  render(<MemoryRouter initialEntries={["/projects/p-demo/content"]}><Routes><Route path="/projects/:id/content" element={<ProjectContentPage />} /></Routes></MemoryRouter>);
  expect(await screen.findByDisplayValue("微沫青柚气泡水 · 330ml 罐装")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "项目内容" })).toBeInTheDocument();
  expect(screen.queryByLabelText("Brief 原文")).not.toBeInTheDocument();
});
