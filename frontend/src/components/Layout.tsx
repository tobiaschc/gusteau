import { BookOpen, CalendarDays, Minus, Moon, Plus, ShoppingBasket, Sun, Users } from "lucide-react"
import { NavLink, Outlet } from "react-router-dom"
import { RotatingQuote, ToqueMark } from "@/components/Brand"
import { useApp } from "@/lib/context"
import { cn } from "@/lib/utils"

const NAV = [
  { to: "/", label: "Plan", icon: CalendarDays, end: true },
  { to: "/recipes", label: "Recetas", icon: BookOpen, end: false },
  { to: "/list", label: "Lista", icon: ShoppingBasket, end: false },
]

export function PeopleStepper({ className }: { className?: string }) {
  const { people, setPeople } = useApp()
  return (
    <div className={cn("flex items-center gap-1 rounded-md border bg-background p-1", className)}>
      <Users className="ml-1.5 h-4 w-4 text-muted-foreground" />
      <button
        aria-label="Menos personas"
        className="rounded p-1 hover:bg-accent disabled:opacity-40"
        onClick={() => setPeople(people - 1)}
        disabled={people <= 1}
      >
        <Minus className="h-3.5 w-3.5" />
      </button>
      <span className="w-5 text-center text-sm font-medium tabular-nums">{people}</span>
      <button aria-label="Más personas" className="rounded p-1 hover:bg-accent" onClick={() => setPeople(people + 1)}>
        <Plus className="h-3.5 w-3.5" />
      </button>
    </div>
  )
}

function ThemeButton() {
  const { theme, toggleTheme } = useApp()
  return (
    <button
      onClick={toggleTheme}
      aria-label="Cambiar tema"
      className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
    >
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  )
}

function Logo() {
  return (
    <NavLink to="/" className="flex items-center gap-2" aria-label="Gusteau, inicio">
      <ToqueMark className="h-8 w-8" />
      <span className="font-serif text-xl font-semibold tracking-tight">Gusteau</span>
    </NavLink>
  )
}

export function Layout() {
  return (
    <div className="flex min-h-dvh">
      {/* Sidebar (desktop) */}
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r bg-sidebar md:flex">
        <div className="flex items-center justify-between border-b p-4">
          <Logo />
          <ThemeButton />
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-card text-foreground shadow-sm ring-1 ring-border [&>svg]:text-brand"
                    : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="space-y-2 border-t p-4">
          <p className="text-xs font-medium text-muted-foreground">Personas</p>
          <PeopleStepper className="w-fit" />
          <div className="pt-3">
            <RotatingQuote />
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b bg-background/80 px-4 py-3 backdrop-blur md:hidden">
          <Logo />
          <div className="flex items-center gap-1">
            <PeopleStepper />
            <ThemeButton />
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-28 pt-6 sm:px-6 md:pb-10 lg:px-10 lg:pt-10">
          <Outlet />
        </main>
      </div>

      {/* Floating bottom nav (mobile) */}
      <nav className="pointer-events-none fixed inset-x-0 bottom-0 z-40 flex justify-center pb-[max(12px,env(safe-area-inset-bottom))] md:hidden">
        <div className="pointer-events-auto flex items-center gap-1 rounded-2xl border bg-background/85 p-1.5 shadow-lg backdrop-blur-md">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex flex-col items-center gap-0.5 rounded-xl px-5 py-1.5 text-[11px] font-medium transition-colors",
                  isActive ? "bg-secondary text-foreground [&>svg]:text-brand" : "text-muted-foreground",
                )
              }
            >
              <Icon className="h-5 w-5" />
              {label}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  )
}
