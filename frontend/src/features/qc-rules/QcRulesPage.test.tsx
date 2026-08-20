import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QcRulesPage } from "./QcRulesPage";

it("shows hard, soft and pending columns plus derived defaults", async () => {
  render(<MemoryRouter initialEntries={["/projects/p-demo/qc"]}><Routes><Route path="/projects/:id/qc" element={<QcRulesPage />} /></Routes></MemoryRouter>);
  expect(await screen.findByRole("heading", { name: /硬规则/ })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /软规则/ })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /待确认/ })).toBeInTheDocument();
  expect(screen.getByText(/来自帖子类型约束 · 默认 QC/)).toBeInTheDocument();
});
