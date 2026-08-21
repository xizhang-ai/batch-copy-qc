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

it("shows a wrapping title field and locates a quoted keyword in the body", async () => {
  const user = userEvent.setup();
  const item = structuredClone(fixtureBoard.items.find((entry) => entry.workflow_status === "human_review")!);
  item.title = "一罐敷到面颈，15分钟把疲惫感按下暂停键";
  item.body = "配方定位为全球前沿超修科技，帮助脆弱状态肌肤进行护理。";
  item.findings = [{
    ...item.findings[0],
    id: "absolute-claim",
    category: "claim",
    message: "使用了带有全球领先暗示的绝对化表述。",
    evidence: "“定位为全球前沿超修科技”",
    suggestion: "避免使用“全球前沿”等暗示全球领先地位的表述。",
    field: undefined,
  }];
  render(<ReviewOverlay item={item} onClose={() => undefined} onItemChange={() => undefined} />);

  const title = screen.getByLabelText("标题");
  expect(title.tagName).toBe("TEXTAREA");
  expect(title).toHaveAttribute("rows", "2");
  expect(screen.getByText("全球前沿")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "定位关键词" }));

  const body = screen.getByLabelText("正文") as HTMLTextAreaElement;
  expect(body).toHaveFocus();
  expect(body.value.slice(body.selectionStart, body.selectionEnd)).toBe("全球前沿");
  expect(screen.getByRole("status")).toHaveTextContent("已定位正文中的关键词：“全球前沿”");
});

it("keeps tag findings in the tag field when the same keyword also appears in the body", async () => {
  const user = userEvent.setup();
  const item = structuredClone(fixtureBoard.items.find((entry) => entry.workflow_status === "human_review")!);
  item.body = "正文先出现 Murad慕拉得，但这不是标签 QC 要定位的位置。";
  item.tags = ["Murad慕拉得", "慕拉得面膜"];
  item.findings = [{
    ...item.findings[0],
    id: "tag-format",
    category: "tags",
    message: "Tags must start with # and contain no spaces",
    evidence: "Murad慕拉得",
    field: undefined,
  }];
  render(<ReviewOverlay item={item} onClose={() => undefined} onItemChange={() => undefined} />);

  await user.click(screen.getByRole("button", { name: "定位关键词" }));

  const tags = screen.getByLabelText("话题标签") as HTMLInputElement;
  expect(tags).toHaveFocus();
  expect(tags.value.slice(tags.selectionStart ?? 0, tags.selectionEnd ?? 0)).toBe("Murad慕拉得");
  expect(screen.getByRole("status")).toHaveTextContent("已定位话题标签中的关键词：“Murad慕拉得”");
});
