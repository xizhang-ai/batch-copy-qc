import { expect, test } from "../../frontend/node_modules/@playwright/test/index.js";

test("从项目 Brief 配置到新生成批次", async ({ page }) => {
  await page.goto("/projects/new");
  await page.getByLabel("项目名称").fill("E2E 清爽气泡水");
  await page.getByLabel("品牌").fill("微沫");
  await page.getByLabel("快消品类").fill("即饮饮料");
  await page.getByRole("button", { name: "建立并添加 Brief" }).click();

  await expect(page.getByRole("heading", { name: "E2E 清爽气泡水" })).toBeVisible();
  await page.getByLabel("Brief 原文").fill("品牌微沫，青柚味气泡水 330ml。禁止减肥、燃脂和零负担。用于午后工位场景。");
  await page.getByRole("button", { name: "AI 拆解 Brief" }).click();
  await expect(page.getByText(/已从\s*粘贴文本\s*拆出/)).toBeVisible();
  await page.getByRole("button", { name: "保存并确认项目内容" }).click();
  await expect(page.getByText("内容已确认")).toBeVisible();
  await page.getByRole("link", { name: /下一步：帖子类型/ }).click();

  await page.getByRole("button", { name: "添加帖子类型" }).first().click();
  await page.getByLabel("帖子类型名称").fill("通勤场景");
  await page.getByLabel("生成数量").fill("2");
  await page.getByText("描述要求", { exact: true }).first().click();
  await page.getByRole("button", { name: "描述要求与默认 QC" }).click();
  await page.getByLabel("标题方向").fill("具体时间与通勤场景");
  await page.getByText("一定要有", { exact: true }).locator("..").getByRole("textbox").fill("青柚味\n330ml");
  await page.getByText("一定不要有", { exact: true }).locator("..").getByRole("textbox").fill("减肥\n燃脂");
  await page.getByRole("button", { name: "保存帖子类型" }).click();
  await page.getByRole("link", { name: /下一步：QC 要求/ }).click();

  await expect(page.getByRole("heading", { name: "准备就绪" })).toBeVisible();
  await expect(page.getByText(/1 个帖子类型 · 计划生成/)).toContainText("2");
  await page.getByRole("link", { name: /开始生成/ }).click();
  await expect(page.getByRole("dialog", { name: "按当前规则重新生成" })).toContainText("通勤场景 · 2 篇");
  await page.getByRole("button", { name: /确认生成第 \d+ 批/ }).click();
  await expect(page.getByRole("heading", { name: "文案看板" })).toBeVisible();
});

test("已有项目展示 AI QC 直通完成和参考画像", async ({ page }) => {
  await page.goto("/projects/p-demo/types");
  await expect(page.getByText("原帖全文与确认后的画像都会进入生成 Prompt。")).toBeVisible();
  await expect(page.getByRole("heading", { name: "可编辑风格画像" })).toBeVisible();
  await expect(page.getByText("确认风格画像")).toBeVisible();

  await page.goto("/projects/p-demo/board");
  await expect(page.getByText("AI 自动通过", { exact: true })).toBeVisible();
  await expect(page.getByText("已完成", { exact: true }).first()).toBeVisible();
});

test("飞书预览只输出已完成文案", async ({ page }) => {
  await page.goto("/projects/p-demo/export");
  await expect(page.getByText("3", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/本次排除：待人工 1 篇/)).toBeVisible();
  await page.getByRole("button", { name: "使用模拟输出" }).click();
  await expect(page.getByText("8月种草·当前批次")).toBeVisible();
});
