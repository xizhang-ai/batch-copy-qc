/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_MODE?: "mock" | "real";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare const __USE_MOCK_API__: boolean;
