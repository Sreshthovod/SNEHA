/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  /** Opt-in: run src/test/live-api.test.ts against a running API. */
  readonly VITE_LIVE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
