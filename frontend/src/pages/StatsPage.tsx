import { BarChart3 } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router-dom"
import { euro } from "@/components/ProductPicker"
import { Card } from "@/components/ui/Card"
import { EmptyState, ErrorBox, Loading, PageHeader } from "@/components/ui/States"
import { api, type Stats } from "@/lib/api"
import { useLoad } from "@/lib/hooks"
import { cn, weekMonday } from "@/lib/utils"

const PERIODS = [
  { weeks: 4, label: "4 sem" },
  { weeks: 13, label: "3 meses" },
  { weeks: 52, label: "1 año" },
  { weeks: 0, label: "Todo" },
]

const shortDate = (d: Date | string) =>
  new Date(d).toLocaleDateString("es-ES", { day: "numeric", month: "short", timeZone: "UTC" })
const dayMonth = (d: Date) => `${d.getUTCDate()}/${d.getUTCMonth() + 1}`
const monthLabel = (m: string) =>
  new Date(`${m}-01T00:00:00Z`).toLocaleDateString("es-ES", { month: "short", year: "2-digit", timeZone: "UTC" })
const approx = (total: number, exact: boolean) => `${exact ? "" : "~"}${euro(total)}`

export function StatsPage() {
  const [weeks, setWeeks] = useState(13)
  const { data, error, loading, reload } = useLoad(() => api.stats(weeks), [weeks])

  return (
    <>
      <PageHeader title="Estadísticas" subtitle={data ? subtitle(data) : undefined}>
        <div className="flex rounded-lg border bg-card p-0.5 text-sm">
          {PERIODS.map((p) => (
            <button
              key={p.weeks}
              onClick={() => setWeeks(p.weeks)}
              className={cn(
                "rounded-md px-3 py-1 transition-colors",
                weeks === p.weeks ? "bg-secondary font-medium text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
      </PageHeader>

      {error && <ErrorBox message={error} onRetry={reload} />}
      {loading && !data ? (
        <Loading />
      ) : (
        data &&
        (data.meals_eaten === 0 && data.spending.weeks.length === 0 ? (
          <EmptyState icon={BarChart3} title="Aún no hay historia que contar">
            Los platos de días pasados cuentan como comidos, y el gasto aparece al pulsar «Compra hecha» en la lista.
          </EmptyState>
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 [&>*]:min-w-0">
            <SpendCard stats={data} />
            <DishesCard stats={data} />
            {data.breakfasts.length > 0 && <BreakfastCard stats={data} />}
            {data.never_eaten.length > 0 && <NeverCard stats={data} />}
          </div>
        ))
      )}
    </>
  )
}

function subtitle(s: Stats) {
  const parts = [`${s.meals_eaten} comidas`]
  if (s.meals_skipped) parts.push(`${s.meals_skipped} sin hacer`)
  if (s.spending.total !== null) parts.push(`${euro(s.spending.total)} gastados`)
  return parts.join(" · ")
}

function SpendCard({ stats }: { stats: Stats }) {
  const [by, setBy] = useState<"week" | "month">("week")
  const sp = stats.spending
  const rows =
    by === "week"
      ? sp.weeks.slice(-12).map((w) => ({ key: w.week, label: dayMonth(weekMonday(w.week)), total: w.total, exact: w.exact }))
      : sp.months.slice(-12).map((m) => ({ key: m.month, label: monthLabel(m.month), total: m.total, exact: m.exact }))
  const max = Math.max(...rows.map((r) => r.total), 1)

  return (
    <Card className="p-5 lg:col-span-2">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="font-serif text-lg font-semibold">Gasto</h2>
          {sp.average_week !== null && (
            <p className="text-sm text-muted-foreground">
              Media <span className="font-medium tabular-nums text-foreground">{euro(sp.average_week)}</span> por semana
            </p>
          )}
        </div>
        {rows.length > 0 && (
          <div className="flex rounded-md border p-0.5 text-xs">
            {(["week", "month"] as const).map((k) => (
              <button
                key={k}
                onClick={() => setBy(k)}
                className={cn("rounded px-2 py-0.5", by === k ? "bg-secondary font-medium" : "text-muted-foreground")}
              >
                {k === "week" ? "Semanas" : "Meses"}
              </button>
            ))}
          </div>
        )}
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Sin compras todavía. Pulsa «Compra hecha» en la{" "}
          <Link to="/list" className="underline underline-offset-2">
            lista
          </Link>{" "}
          después de comprar.
        </p>
      ) : (
        <>
          <div className="flex h-40 items-end gap-1.5" role="img" aria-label="Gasto por periodo">
            {rows.map((r, i) => (
              <div
                key={r.key}
                className={cn(
                  "group h-full min-w-0 flex-1 flex-col items-center justify-end gap-1",
                  i < rows.length - 8 ? "hidden sm:flex" : "flex",
                )}
              >
                <span className="text-[10px] tabular-nums text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 sm:opacity-100">
                  {Math.round(r.total)}
                </span>
                <div
                  title={`${r.label}: ${approx(r.total, r.exact)}`}
                  className={cn("w-full max-w-10 rounded-t-md bg-brand", !r.exact && "bg-brand/45")}
                  style={{ height: `${Math.max((r.total / max) * 100, 3)}%` }}
                />
              </div>
            ))}
          </div>
          <div className="mt-1.5 flex gap-1.5 border-t pt-1.5">
            {rows.map((r, i) => (
              <span
                key={r.key}
                className={cn(
                  "min-w-0 flex-1 truncate text-center text-[10px] text-muted-foreground",
                  i < rows.length - 8 && "hidden sm:block",
                )}
              >
                {r.label}
              </span>
            ))}
          </div>
          <p className="mt-3 flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm bg-brand" /> ticket
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm bg-brand/45" /> estimado Mercadona
            </span>
          </p>
        </>
      )}
    </Card>
  )
}

function DishList({ dishes, limit }: { dishes: Stats["dishes"]; limit: number }) {
  const max = dishes[0]?.count ?? 1
  return (
    <ol className="space-y-2.5">
      {dishes.slice(0, limit).map((d) => (
        <li key={`${d.slug ?? d.title}`} className="text-sm">
          <div className="flex items-baseline justify-between gap-3">
            {d.slug ? (
              <Link to={`/recipes/${d.slug}`} className="min-w-0 truncate hover:underline">
                {d.title}
              </Link>
            ) : (
              <span className="min-w-0 truncate italic text-muted-foreground">{d.title}</span>
            )}
            <span className="shrink-0 tabular-nums text-muted-foreground">
              {d.count}× · {shortDate(d.last)}
            </span>
          </div>
          <div className="mt-1 h-1 overflow-hidden rounded-full bg-secondary">
            <div className="h-full rounded-full bg-brand/70" style={{ width: `${(d.count / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ol>
  )
}

function DishesCard({ stats }: { stats: Stats }) {
  return (
    <Card className="p-5">
      <h2 className="mb-1 font-serif text-lg font-semibold">Platos más repetidos</h2>
      <p className="mb-4 text-xs text-muted-foreground">Comidas y cenas · veces · última vez</p>
      {stats.dishes.length ? (
        <DishList dishes={stats.dishes} limit={10} />
      ) : (
        <p className="text-sm text-muted-foreground">Nada todavía en este periodo.</p>
      )}
    </Card>
  )
}

function BreakfastCard({ stats }: { stats: Stats }) {
  return (
    <Card className="p-5">
      <h2 className="mb-4 font-serif text-lg font-semibold">Desayunos</h2>
      <DishList dishes={stats.breakfasts} limit={5} />
    </Card>
  )
}

function NeverCard({ stats }: { stats: Stats }) {
  const [all, setAll] = useState(false)
  const list = all ? stats.never_eaten : stats.never_eaten.slice(0, 8)
  return (
    <Card className="p-5">
      <h2 className="mb-1 font-serif text-lg font-semibold">Sin estrenar</h2>
      <p className="mb-4 text-xs text-muted-foreground">
        {stats.never_eaten.length === 1
          ? "1 receta de comida o cena que no habéis comido en este periodo"
          : `${stats.never_eaten.length} recetas de comida o cena que no habéis comido en este periodo`}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {list.map((r) => (
          <Link
            key={r.slug}
            to={`/recipes/${r.slug}`}
            className="rounded-full border px-2.5 py-1 text-xs transition-colors hover:bg-accent"
          >
            {r.title}
          </Link>
        ))}
        {!all && stats.never_eaten.length > list.length && (
          <button className="px-2 py-1 text-xs text-muted-foreground underline-offset-2 hover:underline" onClick={() => setAll(true)}>
            +{stats.never_eaten.length - list.length} más
          </button>
        )}
      </div>
    </Card>
  )
}
