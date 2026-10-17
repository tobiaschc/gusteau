/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "pyodide": the backend runs inside the app (mobile build, `--mode mobile`); unset: the HTTP API. */
  readonly VITE_RUNTIME?: "pyodide"
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
