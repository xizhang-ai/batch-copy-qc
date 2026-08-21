import { render, screen } from "@testing-library/react";
import { QcFindingsPanel } from "./QcFindingsPanel";

it("explains and groups legacy tag findings without showing NaN confidence", () => {
  const findings = ["Murad慕拉得", "慕拉得面膜"].map((evidence, index) => ({
    id: `finding-${index}`,
    level: "soft" as const,
    category: "tags",
    status: "open" as const,
    message: "Tags must start with # and contain no spaces",
    evidence,
    suggestion: "",
    field: "tags" as const,
    auto_fixable: true,
    source: "deterministic" as const,
  }));

  render(<QcFindingsPanel findings={findings} onLocate={() => undefined} />);

  expect(screen.getAllByText("话题标签格式需要检查")).toHaveLength(1);
  expect(screen.getByText("格式检查")).toBeInTheDocument();
  expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
  expect(screen.getByText("Murad慕拉得")).toBeInTheDocument();
  expect(screen.getByText("慕拉得面膜")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "定位关键词" })).toBeInTheDocument();
});
