// Messages between the page and the Pyodide worker.
import type { Files, Persist } from "./storage"

export type PyResponse = { status: number; content_type: string; body: string }

export type ToWorker =
  | { type: "init"; files: Files } // the saved data dir; the worker boots once it arrives
  | { type: "request"; id: number; method: string; path: string; body?: string | null }

export type FromWorker =
  | { type: "ready" }
  | { type: "boot-error"; error: string }
  | { type: "persist"; persist: Persist } // files to store: after boot and after each write
  | { type: "reply"; id: number; ok: true; response: PyResponse }
  | { type: "reply"; id: number; ok: false; error: string }
