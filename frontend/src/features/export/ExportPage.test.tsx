import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ExportPage } from "./ExportPage";

it("shows read-only connection status and no credential inputs", async () => {
  render(<MemoryRouter initialEntries={["/projects/p-demo/export"]}><Routes><Route path="/projects/:id/export" element={<ExportPage />} /></Routes></MemoryRouter>);
  expect(await screen.findByRole("heading", { name: "连接状态" })).toBeInTheDocument();
  expect(screen.getByText("模拟连接")).toBeInTheDocument();
  expect(screen.queryByLabelText(/app secret|api key|spreadsheet token/i)).not.toBeInTheDocument();
  expect(screen.getByText("模拟输出")).toBeInTheDocument();
});
