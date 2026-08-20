import { expect, test } from "../../frontend/node_modules/@playwright/test/index.js";

test("真实前后端：项目 Brief 到 Fake AI QC 自动完成", async ({ page }) => {
  await page.goto("/projects/new");
  await page.getByLabel("项目名称").fill("Real E2E 青柚气泡水");
  await page.getByLabel("品牌").fill("微沫测试品牌");
  await page.getByLabel("快消品类").fill("即饮饮料");
  await page.getByRole("button", { name: "建立并添加 Brief" }).click();

  await expect(page.getByRole("heading", { name: "Real E2E 青柚气泡水" })).toBeVisible();
  await page.getByLabel("Brief 原文").fill([
    "产品：青柚气泡水 330ml",
    "人群：办公室通勤人群",
    "事实：青柚味，以包装信息为准",
  ].join("\n"));
  await page.getByRole("button", { name: "AI 拆解 Brief" }).click();
  await expect(page.getByText(/已从.*拆出/)).toBeVisible();
  await page.getByRole("button", { name: "保存并确认项目内容" }).click();
  await expect(page.getByText("内容已确认")).toBeVisible();
  await page.getByRole("link", { name: /下一步：帖子类型/ }).click();

  await page.getByRole("button", { name: "添加帖子类型" }).first().click();
  await page.getByLabel("帖子类型名称").fill("通勤场景实测");
  await page.getByLabel("生成数量").fill("1");
  await page.getByLabel("类型 Brief（可选）").fill("品牌：微沫测试品牌\n补充：活动价待确认");
  await page.getByRole("button", { name: "识别类型 Brief" }).click();
  const projectSuggestions = page.getByRole("region", { name: "项目事实建议", exact: true });
  const conflicts = page.getByRole("region", { name: "冲突与待确认", exact: true });
  await expect(projectSuggestions.getByLabel("识别内容")).toHaveValue("微沫测试品牌");
  await projectSuggestions.getByRole("button", { name: "确认保留" }).click();
  await conflicts.getByRole("button", { name: "忽略" }).click();
  await page.getByText("描述要求", { exact: true }).first().click();
  await page.getByRole("button", { name: "描述要求与默认 QC" }).click();
  await page.getByLabel("标题方向").fill("具体时间与通勤场景");
  await page.getByText("一定要有", { exact: true }).locator("..").getByRole("textbox").fill("青柚味");
  await page.getByText("一定不要有", { exact: true }).locator("..").getByRole("textbox").fill("减肥");
  await page.getByRole("button", { name: "保存帖子类型" }).click();
  await page.reload();
  await expect(page.getByRole("region", { name: "项目事实建议", exact: true }).getByText("已确认")).toBeVisible();
  await expect(page.getByRole("region", { name: "冲突与待确认", exact: true }).getByText("已忽略")).toBeVisible();
  await page.getByRole("link", { name: /下一步：QC 要求/ }).click();

  await expect(page.getByRole("heading", { name: "准备就绪" })).toBeVisible();
  await page.getByRole("link", { name: /开始生成/ }).click();
  const dialog = page.getByRole("dialog", { name: "确认新生成批次" });
  await expect(dialog).toContainText("通勤场景实测 · 1 篇");
  await dialog.getByRole("button", { name: "确认开始" }).click();

  await expect(page.getByRole("heading", { name: "文案看板" })).toBeVisible();
  await expect(page.getByText("AI 自动通过", { exact: true })).toBeVisible({ timeout: 15_000 });

  const projectId = new URL(page.url()).pathname.split("/")[2];
  const boardResponse = await page.request.get(`/api/projects/${projectId}/board`);
  expect(boardResponse.ok()).toBeTruthy();
  const board = await boardResponse.json() as {
    run_id: string;
    items: Array<{ id: string; workflow_status: string; completion_reason?: string }>;
  };
  const generatedItem = board.items.find((item) => item.workflow_status === "completed" && item.completion_reason === "ai_pass");
  expect(generatedItem).toBeTruthy();

  const recallResponse = await page.request.post(`/api/items/${generatedItem!.id}/review`, { data: { action: "recall", reason: "E2E 强制通过路径" } });
  expect(recallResponse.ok()).toBeTruthy();
  await page.reload();
  await page.getByRole("button", { name: "审核" }).click();
  const reviewDialog = page.getByRole("dialog", { name: "人工审核" });
  await reviewDialog.getByLabel("正文").fill("青柚气泡水 330ml，人工复核后保留这条通勤场景描述。青柚味信息以包装为准。");
  await reviewDialog.getByRole("button", { name: "保存修改" }).click();
  await expect(reviewDialog).toBeVisible();
  await expect(reviewDialog.getByText(/版本 2/)).toBeVisible();
  await expect(reviewDialog.getByText("当前没有未解决问题。", { exact: false })).toBeVisible();
  await reviewDialog.getByRole("button", { name: "正常通过" }).click();
  await expect(page.getByText("人工通过", { exact: true })).toBeVisible();

  const secondRecallResponse = await page.request.post(`/api/items/${generatedItem!.id}/review`, { data: { action: "recall", reason: "E2E 再次召回并强制通过" } });
  expect(secondRecallResponse.ok()).toBeTruthy();
  await page.reload();
  await page.getByRole("button", { name: "审核" }).click();
  await page.getByRole("button", { name: "强制通过" }).click();
  const forceDialog = page.getByRole("dialog", { name: "强制通过" });
  const legacyIssues = forceDialog.getByLabel("遗留问题");
  const forceReason = forceDialog.getByLabel("放行理由");
  await legacyIssues.fill("   ");
  await forceReason.fill("   ");
  await expect(forceDialog.getByRole("button", { name: "确认强制通过" })).toBeDisabled();
  await legacyIssues.fill("活动价格仍需上线前人工确认");
  await expect(forceDialog.getByRole("button", { name: "确认强制通过" })).toBeDisabled();
  await forceReason.fill("负责人确认本批次按例外流程放行");
  await forceDialog.getByRole("button", { name: "确认强制通过" }).click();
  await expect(page.getByText("强制通过 · 有遗留问题", { exact: true })).toBeVisible();
  const forcedBoardResponse = await page.request.get(`/api/projects/${projectId}/board`);
  expect(forcedBoardResponse.ok()).toBeTruthy();
  const forcedBoard = await forcedBoardResponse.json() as typeof board;
  expect(forcedBoard.items.find((item) => item.id === generatedItem!.id)).toMatchObject({ workflow_status: "completed", completion_reason: "forced_pass" });

  const exportPayload = {
    export_run_id: "real-e2e-fixed-export",
    generation_run_id: forcedBoard.run_id,
    sheet_title: "Real E2E 小红书文案输出",
  };
  const firstExportResponse = await page.request.post(`/api/projects/${projectId}/exports`, { data: exportPayload });
  const secondExportResponse = await page.request.post(`/api/projects/${projectId}/exports`, { data: exportPayload });
  expect(firstExportResponse.ok()).toBeTruthy();
  expect(secondExportResponse.ok()).toBeTruthy();
  const firstExport = await firstExportResponse.json() as { id: string; sheet_id: string; row_count: number };
  const secondExport = await secondExportResponse.json() as { id: string; sheet_id: string; row_count: number };
  expect(firstExport.row_count).toBeGreaterThan(0);
  expect(secondExport).toMatchObject({
    id: firstExport.id,
    sheet_id: firstExport.sheet_id,
    row_count: firstExport.row_count,
  });
});
