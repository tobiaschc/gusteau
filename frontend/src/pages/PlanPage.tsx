import { Plus, RefreshCw, ShoppingBasket, Sparkles } from "lucide-react"
import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { RecipePicker } from "@/components/RecipePicker"
import { SlotIcon } from "@/components/SlotIcon"
import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { EmptyState, ErrorBox, Loading, PageHeader } from "@/components/ui/States"
import { WeekNav } from "@/components/WeekNav"
import { api } from "@/lib/api"
import { useApp } from "@/lib/context"
import { useLoad } from "@/lib/hooks"
import { cn, DAY_LABELS, SLOT_LABELS, weekMonday } from "@/lib/utils"

export function PlanPage() {
  const { week } = useApp()
  const navigate = useNavigate()
  const plan = useLoad(() => api.plan(week), [week])
  const recipes = useLoad(() => api.recipes(), [])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [picking, setPicking] = useState<{ day: string; slot: string } | null>(null)

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    setError(null)
    try {
      const p = await fn()
      plan.setData(p as typeof plan.data)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const pick = (slug: string | null) => {
    if (!plan.data || !picking) return
    const days = structuredClone(plan.data.days)
    days[picking.day][picking.slot] = slug
    setPicking(null)
    run(() => api.savePlan(week, days))
  }

  const data = plan.data
  const filled = data ? Object.values(data.days).flatMap(Object.values).filter(Boolean).length : 0
  const total = data ? Object.values(data.days).flatMap(Object.values).length : 0
  const monday = weekMonday(week)
  const [today] = useState(() => new Date())

  return (
    <>
      <PageHeader title="Plan semanal" subtitle={data ? `${filled} de ${total} comidas planificadas` : undefined}>
        <WeekNav />
        {filled > 0 && filled < total && (
          <Button variant="outline" onClick={() => run(() => api.generate(week, true))} disabled={busy}>
            <Sparkles /> Completar
          </Button>
        )}
        <Button variant={filled ? "outline" : "default"} onClick={() => run(() => api.generate(week, false))} disabled={busy}>
          {filled ? <RefreshCw className={cn(busy && "animate-spin")} /> : <Sparkles />}
          {filled ? "Regenerar" : "Generar semana"}
        </Button>
        {filled > 0 && (
          <Button variant="brand" className="hidden md:inline-flex" onClick={() => navigate("/list")}>
            <ShoppingBasket /> Lista
          </Button>
        )}
      </PageHeader>

      {(error || plan.error) && <div className="mb-4"><ErrorBox message={(error || plan.error)!} onRetry={plan.reload} /></div>}
      {plan.loading && !data ? (
        <Loading />
      ) : (
        data && (
          <>
          {filled === 0 && (
            <EmptyState className="mb-6 py-6" title="La cocina está en silencio">
              Gusteau diría que cualquiera puede cocinar. Pulsa «Generar semana» y deja que Remy proponga, o elige tú cada plato.
            </EmptyState>
          )}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {Object.entries(data.days).map(([day, slots], i) => {
              const date = new Date(monday)
              date.setUTCDate(monday.getUTCDate() + i)
              const isToday =
                date.getUTCFullYear() === today.getFullYear() &&
                date.getUTCMonth() === today.getMonth() &&
                date.getUTCDate() === today.getDate()
              return (
                <Card key={day} className={cn("p-4", isToday && "ring-2 ring-brand/60")}>
                  <div className="mb-3 flex items-baseline justify-between">
                    <h2 className="font-serif text-[17px] font-semibold">{DAY_LABELS[day] ?? day}</h2>
                    <span className="text-xs text-muted-foreground">
                      {isToday && <span className="mr-1.5 font-medium text-brand">Hoy</span>}
                      {date.toLocaleDateString("es-ES", { day: "numeric", month: "short", timeZone: "UTC" })}
                    </span>
                  </div>
                  <div className="space-y-1">
                    {Object.entries(slots).map(([slot, slug]) => (
                      <div key={slot} className="group flex items-center gap-3 rounded-md p-1.5 transition-colors hover:bg-accent/60">
                        <SlotIcon slot={slot} />
                        <button className="min-w-0 flex-1 text-left" onClick={() => setPicking({ day, slot })}>
                          <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                            {SLOT_LABELS[slot] ?? slot}
                          </div>
                          {slug ? (
                            <div className="line-clamp-2 text-sm font-medium leading-snug">{data.titles[slug] ?? slug}</div>
                          ) : (
                            <div className="flex items-center gap-1 text-sm text-muted-foreground">
                              <Plus className="h-3.5 w-3.5" /> Añadir
                            </div>
                          )}
                        </button>
                        {slug && (
                          <Link
                            to={`/recipes/${slug}`}
                            className="text-xs text-muted-foreground opacity-0 transition-opacity hover:text-foreground group-hover:opacity-100"
                          >
                            Ver
                          </Link>
                        )}
                      </div>
                    ))}
                  </div>
                </Card>
              )
            })}
          </div>
          </>
        )
      )}

      {picking && data && (
        <RecipePicker
          open
          onOpenChange={(o) => !o && setPicking(null)}
          recipes={recipes.data ?? []}
          slot={picking.slot}
          current={data.days[picking.day][picking.slot]}
          title={`${DAY_LABELS[picking.day] ?? picking.day} · ${SLOT_LABELS[picking.slot] ?? picking.slot}`}
          onPick={pick}
        />
      )}
    </>
  )
}
