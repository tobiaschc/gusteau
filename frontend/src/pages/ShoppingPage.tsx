import { Check, Copy, Download, RotateCcw, ShoppingBasket, Store } from "lucide-react"
import { useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { EmptyState, ErrorBox, Loading, PageHeader } from "@/components/ui/States"
import { euro, ProductPicker } from "@/components/ProductPicker"
import { WeekNav } from "@/components/WeekNav"
import { api, type ShoppingItem } from "@/lib/api"
import { useApp } from "@/lib/context"
import { useLoad, useLocalStorage } from "@/lib/hooks"
import { cap, cn } from "@/lib/utils"

export function ShoppingPage() {
  const { week, people } = useApp()
  const { data, error, loading, reload } = useLoad(() => api.shopping(week, people), [week, people])
  const [checked, setChecked] = useLocalStorage<string[]>(`gusteau:checked:${week}`, [])
  const [copied, setCopied] = useState(false)
  const [picking, setPicking] = useState<ShoppingItem | null>(null)

  const groups = useMemo(() => {
    const map = new Map<string, ShoppingItem[]>()
    for (const item of data?.items ?? []) map.set(item.aisle, [...(map.get(item.aisle) ?? []), item])
    return [...map.entries()]
  }, [data])

  const toggle = (name: string) =>
    setChecked(checked.includes(name) ? checked.filter((n) => n !== name) : [...checked, name])

  const asText = () =>
    groups
      .map(
        ([aisle, items]) =>
          `${aisle}\n` +
          items
            .map((i) => {
              const m = i.mercadona
              const product = m && !m.pantry ? ` (${m.packs > 1 ? `${m.packs} × ` : ""}${m.product.name})` : ""
              return `- ${i.name}: ${i.amounts.map((a) => a.label).join(" + ")}${product}`
            })
            .join("\n"),
      )
      .join("\n\n")

  const copy = async () => {
    await navigator.clipboard.writeText(asText())
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const total = data?.items.length ?? 0
  const done = data?.items.filter((i) => checked.includes(i.name)).length ?? 0
  const pending = data?.items
    .filter((i) => !checked.includes(i.name) && i.mercadona && !i.mercadona.pantry)
    .reduce((sum, i) => sum + (i.mercadona?.cost ?? 0), 0)

  return (
    <>
      <PageHeader
        title="Lista de la compra"
        subtitle={
          data
            ? [
                `${data.meals} comidas`,
                `${total} ingredientes`,
                `${done} en el carro`,
                data.total !== null && `~${euro(data.total)} en Mercadona`,
              ]
                .filter(Boolean)
                .join(" · ")
            : undefined
        }
      >
        <WeekNav />
      </PageHeader>

      {error && <ErrorBox message={error} onRetry={reload} />}
      {loading && !data ? (
        <Loading />
      ) : data && total === 0 ? (
        <EmptyState
          icon={ShoppingBasket}
          title="La despensa espera"
          action={
            <Link to="/">
              <Button>Ir al plan</Button>
            </Link>
          }
        >
          Esta semana no tiene comidas planificadas. Sin plan no hay mercado: planifica y Remy hará la lista.
        </EmptyState>
      ) : (
        data && (
          <>
            {data.prices_error && (
              <p className="mb-4 rounded-lg border border-dashed px-3 py-2 text-sm text-muted-foreground">
                Sin precios de Mercadona ahora mismo: la lista funciona igual. ({data.prices_error})
              </p>
            )}
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <div className="h-1.5 min-w-[8rem] flex-1 overflow-hidden rounded-full bg-secondary">
                <div className="h-full bg-brand transition-all" style={{ width: `${total ? (done / total) * 100 : 0}%` }} />
              </div>
              {data.total !== null && done > 0 && !!pending && (
                <span className="text-sm tabular-nums text-muted-foreground">quedan ~{euro(pending)}</span>
              )}
              <Button variant="outline" size="sm" onClick={copy}>
                {copied ? <Check /> : <Copy />} {copied ? "Copiada" : "Copiar"}
              </Button>
              <a href={`/api/plans/${week}/shopping.md?people=${people}`} download={`lista-${week}.md`}>
                <Button variant="outline" size="sm">
                  <Download /> .md
                </Button>
              </a>
              {done > 0 && (
                <Button variant="ghost" size="sm" onClick={() => setChecked([])}>
                  <RotateCcw /> Desmarcar
                </Button>
              )}
            </div>
            <div className="columns-1 gap-4 md:columns-2 xl:columns-3">
              {groups.map(([aisle, items]) => (
                <Card key={aisle} className="mb-4 break-inside-avoid p-4">
                  <h2 className="mb-2 font-serif text-[15px] font-semibold text-muted-foreground">{aisle}</h2>
                  <ul>
                    {items.map((item) => {
                      const on = checked.includes(item.name)
                      const m = item.mercadona
                      return (
                        <li key={item.name} className="rounded-md transition-colors hover:bg-accent/60">
                          <button
                            onClick={() => toggle(item.name)}
                            title={`En: ${item.recipes.join(", ")}`}
                            className="flex w-full items-center gap-3 px-1.5 pb-1 pt-2 text-left"
                          >
                            <span
                              className={cn(
                                "flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition-colors",
                                on ? "border-brand bg-brand text-brand-foreground" : "border-input",
                              )}
                            >
                              {on && <Check className="h-3.5 w-3.5" />}
                            </span>
                            <span className={cn("flex-1", on && "text-muted-foreground line-through")}>{cap(item.name)}</span>
                            <span className={cn("text-sm tabular-nums text-muted-foreground", on && "line-through")}>
                              {item.amounts.map((a) => a.label).join(" + ")}
                            </span>
                          </button>
                          {data.prices_error === null && (
                            <button
                              onClick={() => setPicking(item)}
                              className={cn(
                                "flex w-full items-center gap-1.5 pb-2 pl-9 pr-1.5 text-left text-xs text-muted-foreground hover:text-foreground",
                                on && "opacity-50",
                              )}
                            >
                              <Store className="h-3 w-3 shrink-0" />
                              {m ? (
                                <>
                                  <span className="min-w-0 flex-1 truncate">
                                    {m.packs > 1 && `${m.packs} × `}
                                    {m.product.name}
                                    {m.pantry && " · ¿en casa?"}
                                  </span>
                                  <span className={cn("tabular-nums", m.pantry && "line-through decoration-muted-foreground/50")}>
                                    {m.approx && "~"}
                                    {euro(m.cost)}
                                  </span>
                                </>
                              ) : (
                                <span className="flex-1 italic">Elegir producto</span>
                              )}
                            </button>
                          )}
                        </li>
                      )
                    })}
                  </ul>
                </Card>
              ))}
            </div>
            <ProductPicker key={picking?.name} item={picking} onOpenChange={(o) => o || setPicking(null)} onSaved={reload} />
          </>
        )
      )}
    </>
  )
}
