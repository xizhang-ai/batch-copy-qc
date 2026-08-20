import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, vi } from "vitest";
import { api } from "../../api/service";
import { fixtureBoard } from "../../api/fixtures";
import { ReviewOverlay } from "./ReviewOverlay";

afterEach(() => vi.restoreAllMocks());

it("keeps the fixed action order and lets ForcePassDialog restore focus after Escape", async () => {
  const user = userEvent.setup();
  const item = fixtureBoard.items.find((entry) => entry.workflow_status === "human_review")!;
  render(<ReviewOverlay item={item} onClose={() => undefined} onItemChange={() => undefined} />);
  const footer = screen.getByRole("button", { name: "保存修改" }).parentElement!;
  expect(Array.from(footer.querySelectorAll("button")).map((button) => button.textContent)).toEqual(["保存修改", "未通过", "强制通过", "正常通过"]);
  const forceTrigger = screen.getByRole("button", { name: "强制通过" });
  await user.click(forceTrigger);
  const issues = screen.getByLabelText("遗留问题");
  const reason = screen.getByLabelText("放行理由");
  expect(screen.getByRole("button", { name: "确认强制通过" })).toBeDisabled();
  await user.type(reason, "负责人确认本次例外放行");
  await user.clear(issues);
  expect(screen.getByRole("button", { name: "确认强制通过" })).toBeDisabled();
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("dialog", { name: "强制通过" })).not.toBeInTheDocument();
  expect(screen.getByRole("dialog", { name: "人工审核" })).toBeInTheDocument();
  expect(forceTrigger).toHaveFocus();
});

it("lets SelectionRewriteDialog handle Escape and return focus to its trigger", async () => {
  const user = userEvent.setup();
  const item = fixtureBoard.items.find((entry) => entry.workflow_status === "human_review")!;
  render(<ReviewOverlay item={item} onClose={() => undefined} onItemChange={() => undefined} />);
  const body = screen.getByLabelText("正文") as HTMLTextAreaElement;
  body.focus();
  body.setSelectionRange(0, 4);
  fireEvent.select(body);
  const rewriteTrigger = await screen.findByRole("button", { name: /让 AI 修改/ });
  await user.click(rewriteTrigger);
  expect(screen.getByRole("dialog", { name: "让 AI 定向修改" })).toBeInTheDocument();
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("dialog", { name: "让 AI 定向修改" })).not.toBeInTheDocument();
  expect(screen.getByRole("dialog", { name: "人工审核" })).toBeInTheDocument();
  expect(rewriteTrigger).toHaveFocus();
});

it("merges a partial save response and refreshes fresh findings without closing the panel", async () => {
  const user = userEvent.setup();
  const item = structuredClone(fixtureBoard.items.find((entry) => entry.workflow_status === "human_review")!);
  const freshFinding = { ...item.findings[0], id: "fresh-finding", message: "最新 QC：仍需确认活动价格", evidence: "活动价格" };
  vi.spyOn(api, "saveItem").mockResolvedValue({ id: item.id, body: "服务端已保存的正文", version: item.version + 1 });
  const getItem = vi.spyOn(api, "getItem").mockResolvedValue({ id: item.id, findings: [freshFinding] });
  const onItemChange = vi.fn();
  render(<ReviewOverlay item={item} onClose={() => undefined} onItemChange={onItemChange} />);

  await user.clear(screen.getByLabelText("正文"));
  await user.type(screen.getByLabelText("正文"), "人工编辑正文");
  await user.click(screen.getByRole("button", { name: "保存修改" }));

  await waitFor(() => expect(getItem).toHaveBeenCalledWith(item.id));
  expect(screen.getByRole("dialog", { name: "人工审核" })).toBeInTheDocument();
  expect(screen.getByText("最新 QC：仍需确认活动价格")).toBeInTheDocument();
  expect(screen.getByLabelText("正文")).toHaveValue("服务端已保存的正文");
  expect(screen.getByText(new RegExp(item.copy_type_name))).toBeInTheDocument();
  expect(onItemChange).toHaveBeenLastCalledWith(expect.objectContaining({ copy_type_name: item.copy_type_name, findings: [freshFinding], version: item.version + 1 }));
});
