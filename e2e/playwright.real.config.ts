import { defineConfig, devices } from "../frontend/node_modules/@playwright/test/index.js";

export default defineConfig({
  testDir: "./specs",
  testMatch: "real-stack.spec.ts",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  outputDir: "../test-results/real-e2e-artifacts",
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4177",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [{ name: "real-stack-chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/e2e-backend.ps1",
      cwd: "..",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npm.cmd --prefix frontend run dev -- --host 127.0.0.1 --port 4177",
      cwd: "..",
      url: "http://127.0.0.1:4177",
      reuseExistingServer: false,
      timeout: 120_000,
      env: { VITE_API_MODE: "real" },
    },
  ],
});
