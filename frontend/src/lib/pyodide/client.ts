// fetch()-compatible access to the in-app backend: same paths and Response objects as the HTTP API,
// answered by the Pyodide worker instead of a server. The page owns persistence: it hands the worker the saved
// data dir at boot and stores the files each write changed, one save at a time.
import type { FromWorker, PyResponse, ToWorker } from "./protocol"
import { type DataStore, indexedDbStore, type Persist } from "./storage"

let worker: Worker | null = null
let booted: Promise<void> = Promise.resolve()
let seq = 0
const pending = new Map<number, { resolve: (r: PyResponse) => void; reject: (e: Error) => void }>()

const store: DataStore = indexedDbStore()
let saving: Promise<void> = Promise.resolve()

function persist(changes: Persist) {
  saving = saving.then(() => store.apply(changes)).catch((err) => console.error("Gusteau: could not save data", err))
}

function send(msg: ToWorker) {
  // oxlint-disable-next-line unicorn/require-post-message-target-origin -- Worker: 2nd arg is the transfer list
  getWorker().postMessage(msg)
}

function getWorker(): Worker {
  if (worker) return worker
  const w = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" })
  worker = w
  let markReady!: () => void
  let markFailed!: (e: Error) => void
  booted = new Promise<void>((resolve, reject) => ((markReady = resolve), (markFailed = reject)))

  w.addEventListener("message", ({ data }: MessageEvent<FromWorker>) => {
    if (data.type === "ready") return markReady()
    if (data.type === "boot-error") return markFailed(new Error(data.error))
    if (data.type === "persist") return persist(data.persist)
    const call = pending.get(data.id)
    if (!call) return
    pending.delete(data.id)
    if (data.ok) call.resolve(data.response)
    else call.reject(new Error(data.error))
  })

  // Never boot from an empty data dir because storage failed to load: the first save would overwrite the real data.
  store.load().then(
    (files) => send({ type: "init", files }),
    (err) => {
      markFailed(new Error(`no se pudieron leer los datos guardados (${err})`))
      w.terminate()
    },
  )
  return w
}

/** Resolves once the in-app backend has booted (rejects if it can't). */
export function backendReady(): Promise<void> {
  getWorker()
  return booted
}

export function pyFetch(path: string, init?: RequestInit): Promise<Response> {
  const id = ++seq
  return new Promise<PyResponse>((resolve, reject) => {
    pending.set(id, { resolve, reject })
    send({
      type: "request",
      id,
      method: init?.method ?? "GET",
      path,
      body: typeof init?.body === "string" ? init.body : null,
    })
    booted.catch((err: Error) => {
      if (pending.delete(id)) reject(err)
    })
  }).then(({ status, content_type, body }) => {
    const empty = status === 204 || status === 304 // a Response with these statuses can't have a body
    return new Response(empty ? null : body, { status, headers: { "Content-Type": content_type } })
  })
}
