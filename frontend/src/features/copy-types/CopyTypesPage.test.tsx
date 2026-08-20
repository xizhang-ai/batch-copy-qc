import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { CopyTypesPage } from "./CopyTypesPage";

it("starts an unconfigured project with no templates or suggested types", async () => {
  render(<MemoryRouter initialEntries={["/projects/p-empty/types"]}><Routes><Route path="/projects/:id/types" element={<CopyTypesPage />} /></Routes></MemoryRouter>);
  expect(await screen.findByText("还没有帖子类型")).toBeInTheDocument();
  expect(screen.getAllByText("添加帖子类型").length).toBeGreaterThan(0);
  expect(screen.queryByText(/系统模板|模板市场/)).not.toBeInTheDocument();
  await waitFor(() => expect(screen.queryByLabelText("正在加载")).not.toBeInTheDocument());
});

it("shows, edits and restores each type Brief review decision", async () => {
  const user = userEvent.setup();
  const view = render(<MemoryRouter initialEntries={["/projects/p-demo/types"]}><Routes><Route path="/projects/:id/types" element={<CopyTypesPage />} /></Routes></MemoryRouter>);
  expect(await screen.findByDisplayValue("通勤包里常备")).toBeInTheDocument();
  expect(screen.getByLabelText("生成数量")).toHaveAttribute("max", "100");
  await user.click(screen.getByRole("button", { name: "识别类型 Brief" }));

  const projectSuggestions = await screen.findByLabelText("项目事实建议");
  const conflicts = screen.getByLabelText("冲突与待确认");
  const projectValue = within(projectSuggestions).getByLabelText("识别内容");
  await user.clear(projectValue);
  await user.type(projectValue, "品牌建议已编辑");
  await user.click(within(projectSuggestions).getByRole("button", { name: "确认保留" }));
  await user.click(within(conflicts).getByRole("button", { name: "忽略" }));
  await user.click(screen.getByRole("button", { name: "保存帖子类型" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "保存帖子类型" })).toBeEnabled());

  view.unmount();
  render(<MemoryRouter initialEntries={["/projects/p-demo/types"]}><Routes><Route path="/projects/:id/types" element={<CopyTypesPage />} /></Routes></MemoryRouter>);
  expect(await screen.findByDisplayValue("品牌建议已编辑")).toBeInTheDocument();
  expect(within(screen.getByLabelText("项目事实建议")).getByText("已确认")).toBeInTheDocument();
  expect(within(screen.getByLabelText("冲突与待确认")).getByText("已忽略")).toBeInTheDocument();
});

it("persists assigning and clearing a classified file", async () => {
  const user = userEvent.setup();
  const route = <MemoryRouter initialEntries={["/projects/p-demo/types"]}><Routes><Route path="/projects/:id/types" element={<CopyTypesPage />} /></Routes></MemoryRouter>;
  const first = render(route);
  const select = await screen.findByLabelText("聚餐场景参考.md归属");
  await user.selectOptions(select, "ct-commute");
  await waitFor(() => expect(select).toHaveValue("ct-commute"));
  first.unmount();

  const second = render(route);
  expect(await screen.findByLabelText("聚餐场景参考.md归属")).toHaveValue("ct-commute");
  await user.selectOptions(screen.getByLabelText("聚餐场景参考.md归属"), "");
  await waitFor(() => expect(screen.getByLabelText("聚餐场景参考.md归属")).toHaveValue(""));
  second.unmount();

  render(route);
  expect(await screen.findByLabelText("聚餐场景参考.md归属")).toHaveValue("");
});
