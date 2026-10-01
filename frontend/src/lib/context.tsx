import { createContext, useCallback, useContext, useEffect, useState } from "react"
import { api } from "@/lib/api"
import { isoWeek } from "@/lib/utils"

type Ctx = {
  week: string
  setWeek: (w: string) => void
  people: number
  setPeople: (n: number) => void
  theme: "light" | "dark"
  toggleTheme: () => void
}

const AppContext = createContext<Ctx | null>(null)

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [week, setWeek] = useState(isoWeek())
  const [people, setPeopleState] = useState(2)
  const [theme, setTheme] = useState<"light" | "dark">(
    document.documentElement.classList.contains("dark") ? "dark" : "light",
  )

  useEffect(() => {
    api.settings().then((s) => setPeopleState(s.people)).catch(() => {})
  }, [])

  const setPeople = useCallback((n: number) => {
    const v = Math.min(20, Math.max(1, n))
    setPeopleState(v)
    api.saveSettings({ people: v }).catch(() => {})
  }, [])

  const toggleTheme = useCallback(() => {
    setTheme((t) => {
      const next = t === "dark" ? "light" : "dark"
      document.documentElement.classList.toggle("dark", next === "dark")
      localStorage.theme = next
      return next
    })
  }, [])

  return (
    <AppContext.Provider value={{ week, setWeek, people, setPeople, theme, toggleTheme }}>
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error("useApp outside AppProvider")
  return ctx
}
