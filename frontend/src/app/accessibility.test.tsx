import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { BoardPage } from "../features/board/BoardPage";

it("keeps icon actions labelled and task cards keyboard focusable", async () => {
  const { container } = render(<MemoryRouter initialEntries={["/projects/p-demo/board"]}><Routes><Route path="/projects/:id/board" element={<BoardPage />} /></Routes></MemoryRouter>);
  expect(await screen.findByText("XHS-0045")).toBeInTheDocument();
  expect(container.querySelectorAll("[draggable=true]")).toHaveLength(0);
  expect(container.querySelectorAll("article[tabindex='0']").length).toBeGreaterThan(0);
  for (const button of container.querySelectorAll("button")) {
    expect(button.textContent?.trim() || button.getAttribute("aria-label")).toBeTruthy();
  }
});
