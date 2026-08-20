import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppShell } from "./AppShell";

it("renders the fixed workflow navigation in order", () => {
  render(<MemoryRouter><AppShell /></MemoryRouter>);
  const nav = screen.getByRole("navigation", { name: "项目流程" });
  expect(nav.textContent).toBe("项目帖子类型QC 要求文案看板飞书输出");
});
