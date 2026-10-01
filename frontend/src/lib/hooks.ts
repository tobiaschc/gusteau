import { useCallback, useEffect, useState } from "react"

/** Minimal data loader: { data, error, loading, reload, setData }. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const load = useCallback(fn, deps)

  const reload = useCallback(() => {
    setLoading(true)
    return load()
      .then((d) => {
        setData(d)
        setError(null)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [load])

  useEffect(() => {
    reload()
  }, [reload])

  return { data, error, loading, reload, setData }
}

export function useLocalStorage<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key)
      return raw ? (JSON.parse(raw) as T) : initial
    } catch {
      return initial
    }
  })
  useEffect(() => {
    try {
      const raw = localStorage.getItem(key)
      setValue(raw ? (JSON.parse(raw) as T) : initial)
    } catch {
      setValue(initial)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  const set = useCallback(
    (v: T) => {
      setValue(v)
      localStorage.setItem(key, JSON.stringify(v))
    },
    [key],
  )
  return [value, set] as const
}
