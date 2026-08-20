import { defineConfig, devices } from "../frontend/node_modules/@playwright/test/index.js";

export default defineConfig({
  testDir: "./specs",
  testIgnore: "real-stack.spec.ts",
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  expect: { timeout: 8_000 },
  outputDir: "../test-results/e2e-artifacts",
  reporter: [["list"], ["html", { outputFolder: "../playwright-report", open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:4176",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm.cmd --prefix frontend run dev -- --host 127.0.0.1 --port 4176",
    cwd: "..",
    url: "http://127.0.0.1:4176",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: { VITE_API_MODE: "mock" },
  },
});
