import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { BoardPage } from "./BoardPage";

it("always renders five columns and consistent AI processing count", async () => {
  render(<MemoryRouter initialEntries={["/projects/p-demo/board"]}><Routes><Route path="/projects/:id/board" element={<BoardPage />} /></Routes></MemoryRouter>);
  expect(await screen.findByRole("heading", { name: "待 AI QC" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "AI QC 中" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "AI 修改中" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "待人工审核" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "已完成" })).toBeInTheDocument();
  const stats = screen.getByRole("region", { name: "看板统计" });
  expect(stats).toHaveTextContent("AI 处理中2");
  expect(screen.getByText("AI 自动通过")).toBeInTheDocument();
  expect(screen.getByText("人工通过")).toBeInTheDocument();
  expect(screen.getByText("强制通过 · 有遗留问题")).toBeInTheDocument();
});
