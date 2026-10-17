/// <reference lib="webworker" />
// Runs the Gusteau backend (FastAPI + SQLite) inside Pyodide, off the main thread. Assets come from
// public-mobile/pyodide/ (built by scripts/build_pyodide.py), so nothing is fetched from a CDN at runtime.
// The data dir lives in memory: it is rebuilt from the files the page sends with "init", and every write reports
// the files it changed ("persist") for the page to store.
import { loadPyodide } from "pyodide"
import type { FromWorker, ToWorker } from "./protocol"
import type { Files, Persist } from "./storage"

type Manifest = { pyodide: string; packages: string[]; wheels: string[]; app: string }
type App = {
  request_json(method: string, path: string, body: string | null): Promise<string>
  snapshot_json(): string
}

const BASE = new URL(`${import.meta.env.BASE_URL}pyodide/`, self.location.origin).href

function post(msg: FromWorker) {
  // oxlint-disable-next-line unicorn/require-post-message-target-origin -- worker scope: no origin argument
  self.postMessage(msg)
}

function postPersist(persist: Persist) {
  if (Object.keys(persist.changed).length || persist.deleted.length) post({ type: "persist", persist })
}

async function boot(files: Files): Promise<App> {
  const manifest: Manifest = await (await fetch(`${BASE}manifest.json`, { cache: "no-cache" })).json()
  const py = await loadPyodide({ indexURL: BASE })
  const quiet = { messageCallback: () => {} }
  await py.loadPackage(manifest.packages, quiet)
  await py.loadPackage(
    manifest.wheels.map((w) => BASE + w),
    quiet,
  )
  const bundle = await (await fetch(BASE + manifest.app, { cache: "no-cache" })).arrayBuffer()
  py.unpackArchive(bundle, "zip", { extractDir: "/app" })
  py.globals.set("saved_files", JSON.stringify(files))
  await py.runPythonAsync(`
import json, sys
sys.path.insert(0, "/app")
from gusteau.mobile import MobileApp
app = MobileApp("/data", json.loads(saved_files))
del saved_files
`)
  const app = py.globals.get("app") as App
  postPersist(JSON.parse(app.snapshot_json())) // first launch, recipe sync and migrations write files too
  return app
}

let receivedFiles: (files: Files) => void
const ready = new Promise<Files>((resolve) => (receivedFiles = resolve)).then(boot)
ready.then(
  () => post({ type: "ready" }),
  (err) => post({ type: "boot-error", error: err instanceof Error ? err.message : String(err) }),
)

self.addEventListener("message", async ({ data }: MessageEvent<ToWorker>) => {
  if (data.type === "init") return receivedFiles(data.files)
  try {
    const app = await ready
    const out = JSON.parse(await app.request_json(data.method, data.path, data.body ?? null))
    if (out.persist) postPersist(out.persist) // before the reply, so the page queues the save first
    post({ type: "reply", id: data.id, ok: true, response: out.response })
  } catch (err) {
    post({ type: "reply", id: data.id, ok: false, error: err instanceof Error ? err.message : String(err) })
  }
})
