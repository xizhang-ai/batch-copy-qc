import { expect, test } from "../../frontend/node_modules/@playwright/test/index.js";

test("人工直接修改后正常通过", async ({ page }) => {
  await page.goto("/projects/p-demo/board");
  await page.getByRole("button", { name: "审核" }).click();
  await expect(page.getByRole("dialog", { name: "人工审核" })).toBeVisible();

  const body = page.getByLabel("正文");
  await body.fill("下午容易犯困的时候，我会喝一罐冰冰的青柚气泡水。330ml 不占地方，青柚味很清新。入口不会太甜。包装信息均以项目事实为准。");
  await page.getByRole("button", { name: "保存修改" }).click();
  await expect(page.getByRole("button", { name: "正常通过" })).toBeEnabled();
  await page.getByRole("button", { name: "正常通过" }).click();
  await expect(page.getByRole("dialog", { name: "人工审核" })).not.toBeVisible();
  await expect(page.getByLabel("XHS-0045 午后想喝点有味道的").getByText("人工通过", { exact: true })).toBeVisible();
});

test("强制通过必须分别填写遗留问题和放行理由", async ({ page }) => {
  await page.goto("/projects/p-demo/board");
  await page.getByRole("button", { name: "审核" }).click();
  await page.getByRole("button", { name: "强制通过" }).click();
  const dialog = page.getByRole("dialog", { name: "强制通过" });
  const issues = dialog.getByLabel("遗留问题");
  const reason = dialog.getByLabel("放行理由");

  await issues.fill("   ");
  await reason.fill("   ");
  await expect(dialog.getByRole("button", { name: "确认强制通过" })).toBeDisabled();
  await issues.fill("活动价格仍需人工确认");
  await expect(dialog.getByRole("button", { name: "确认强制通过" })).toBeDisabled();
  await reason.fill("本批次经负责人确认按例外流程放行");
  await dialog.getByRole("button", { name: "确认强制通过" }).click();
  await expect(page.getByText("强制通过 · 有遗留问题", { exact: true })).toBeVisible();
});
