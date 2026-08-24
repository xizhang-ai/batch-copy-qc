import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppShell } from "./AppShell";

it("renders the task-first primary navigation", () => {
  render(<MemoryRouter><AppShell /></MemoryRouter>);
  const nav = screen.getByRole("navigation", { name: "项目流程" });
  expect(nav.textContent).toBe("工作台文案看板飞书输出");
});
