import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const fileEnv = loadEnv(mode, process.cwd(), "VITE_");
  const explicitMode = process.env.VITE_API_MODE ?? fileEnv.VITE_API_MODE;
  const useMock = mode === "test" || explicitMode === "mock";
  return {
    plugins: [react()],
    define: { __USE_MOCK_API__: JSON.stringify(useMock) },
    server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } },
    test: { environment: "jsdom", setupFiles: "./src/test/setup.ts", css: true, globals: true, env: { VITE_API_MODE: "mock" } },
  };
});
