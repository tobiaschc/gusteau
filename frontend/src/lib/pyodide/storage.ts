// Where the in-app backend's data dir lives between launches. The worker's file system is in memory, so the page
// restores it at boot and stores the files each write changed (relative path -> base64 content).
export type Files = Record<string, string>
export type Persist = { changed: Files; deleted: string[] }

export interface DataStore {
  load(): Promise<Files>
  apply(persist: Persist): Promise<void>
}

const DB = "gusteau"
const STORE = "files"

function promised<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.addEventListener("success", () => resolve(req.result))
    req.addEventListener("error", () => reject(req.error))
  })
}

/** Browser storage: IndexedDB, used both in a desktop browser and on the phone (Safari/Chrome also implement it). */
export function indexedDbStore(): DataStore {
  let opened: Promise<IDBDatabase> | null = null
  const open = () => {
    if (!opened) {
      const req = indexedDB.open(DB, 1)
      req.addEventListener("upgradeneeded", () => req.result.createObjectStore(STORE))
      opened = promised(req)
    }
    return opened
  }
  return {
    async load() {
      const db = await open()
      const tx = db.transaction(STORE, "readonly").objectStore(STORE)
      const [keys, values] = await Promise.all([promised(tx.getAllKeys()), promised(tx.getAll())])
      return Object.fromEntries(keys.map((k, i) => [String(k), values[i] as string]))
    },
    async apply({ changed, deleted }) {
      const db = await open()
      const tx = db.transaction(STORE, "readwrite")
      const files = tx.objectStore(STORE)
      for (const [path, content] of Object.entries(changed)) files.put(content, path)
      for (const path of deleted) files.delete(path)
      await new Promise<void>((resolve, reject) => {
        tx.addEventListener("complete", () => resolve())
        tx.addEventListener("error", () => reject(tx.error))
        tx.addEventListener("abort", () => reject(tx.error))
      })
    },
  }
}
