import { Check, Copy, Download, House, RotateCcw, ShoppingBasket, Store, Undo2 } from "lucide-react"
import { useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { EmptyState, ErrorBox, Loading, PageHeader } from "@/components/ui/States"
import { euro, ProductPicker } from "@/components/ProductPicker"
import { PurchaseBar } from "@/components/PurchaseBar"
import { WeekNav } from "@/components/WeekNav"
import { api, type Shopping, type ShoppingItem } from "@/lib/api"
import { useApp } from "@/lib/context"
import { useLoad } from "@/lib/hooks"
import { cap, cn } from "@/lib/utils"

type Marks = Partial<Pick<ShoppingItem, "in_cart" | "at_home">>

const amountLabel = (i: ShoppingItem) => i.amounts.map((a) => a.label).join(" + ")
/** On the list proper: everything except pantry items we have (or haven't checked yet). */
const toBuy = (i: ShoppingItem) => !i.pantry || i.at_home === false

export function ShoppingPage() {
  const { week, people } = useApp()
  const { data, error, loading, reload, setData } = useLoad(() => api.shopping(week, people), [week, people])
  const [copied, setCopied] = useState(false)
  const [picking, setPicking] = useState<ShoppingItem | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

  const buy = useMemo(() => data?.items.filter(toBuy) ?? [], [data])
  const ask = data?.items.filter((i) => i.pantry && i.at_home === null) ?? []
  const have = data?.items.filter((i) => i.pantry && i.at_home === true) ?? []

  const groups = useMemo(() => {
    const map = new Map<string, ShoppingItem[]>()
    for (const item of buy) map.set(item.aisle, [...(map.get(item.aisle) ?? []), item])
    return [...map.entries()]
  }, [buy])

  // Optimistic: update the screen now, then the shared state; on failure, reload the truth.
  const patch = (fn: (d: Shopping) => Shopping, save: () => Promise<unknown>) => {
    if (!data) return
    setData(fn(data))
    setSaveError(null)
    save().catch((e: Error) => {
      setSaveError(e.message)
      reload()
    })
  }
  const mark = (name: string, m: Marks) =>
    patch(
      (d) => ({ ...d, items: d.items.map((i) => (i.name === name ? { ...i, ...m } : i)) }),
      () => api.mark(week, name, m),
    )
  const clearCart = () =>
    patch(
      (d) => ({ ...d, items: d.items.map((i) => ({ ...i, in_cart: false })) }),
      () => api.clearCart(week),
    )

  const asText = () =>
    groups
      .map(
        ([aisle, items]) =>
          `${aisle}\n` +
          items
            .map((i) => {
              const m = i.mercadona
              const product = m ? ` (${m.packs > 1 ? `${m.packs} × ` : ""}${m.product.name})` : ""
              return `- ${i.name}: ${amountLabel(i)}${product}`
            })
            .join("\n"),
      )
      .join("\n\n")

  const copy = async () => {
    await navigator.clipboard.writeText(asText())
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const total = buy.length
  const done = buy.filter((i) => i.in_cart).length
  const pending = buy.filter((i) => !i.in_cart).reduce((sum, i) => sum + (i.mercadona?.cost ?? 0), 0)
  const prices = data?.prices_error === null

  return (
    <>
      <PageHeader
        title="Lista de la compra"
        subtitle={
          data
            ? [
                `${data.meals} comidas`,
                `${total} productos`,
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

      {(error || saveError) && <ErrorBox message={(error ?? saveError)!} onRetry={reload} />}
      {loading && !data ? (
        <Loading />
      ) : data && data.items.length === 0 ? (
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
                <Button variant="ghost" size="sm" onClick={clearCart}>
                  <RotateCcw /> Desmarcar
                </Button>
              )}
            </div>
            <PurchaseBar week={week} people={people} />

            {ask.length > 0 && (
              <Card className="mb-4 border-dashed p-4">
                <h2 className="flex items-center gap-2 font-serif text-[15px] font-semibold">
                  <House className="h-4 w-4 text-brand" /> ¿Lo tienes en casa?
                  <span className="font-sans text-xs font-normal text-muted-foreground">{ask.length}</span>
                </h2>
                <p className="mb-2 mt-0.5 text-xs text-muted-foreground">
                  Se usa poco de cada uno. Si te falta algo, pasa a la lista.
                </p>
                <ul className="divide-y divide-border/60">
                  {ask.map((item) => (
                    <li key={item.name} className="flex items-center gap-2 py-1.5">
                      <span className="min-w-0 flex-1 truncate" title={`En: ${item.recipes.join(", ")}`}>
                        {cap(item.name)}
                      </span>
                      <Button variant="ghost" size="sm" onClick={() => mark(item.name, { at_home: true })}>
                        Lo tengo
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => mark(item.name, { at_home: false })}>
                        Me falta
                      </Button>
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            <div className="columns-1 gap-4 md:columns-2 xl:columns-3">
              {groups.map(([aisle, items]) => (
                <Card key={aisle} className="mb-4 break-inside-avoid p-4">
                  <h2 className="mb-2 font-serif text-[15px] font-semibold text-muted-foreground">{aisle}</h2>
                  <ul>
                    {items.map((item) => {
                      const on = item.in_cart
                      const m = item.mercadona
                      return (
                        <li key={item.name} className="rounded-md transition-colors hover:bg-accent/60">
                          <button
                            onClick={() => mark(item.name, { in_cart: !on })}
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
                              {amountLabel(item)}
                            </span>
                          </button>
                          {item.pantry && (
                            <button
                              onClick={() => mark(item.name, { at_home: null, in_cart: false })}
                              title="Deshacer: volver a preguntar"
                              className="ml-9 inline-flex items-center gap-1 rounded-full bg-secondary px-2 py-0.5 text-[11px] text-muted-foreground hover:text-foreground"
                            >
                              <House className="h-3 w-3" /> faltaba <Undo2 className="h-3 w-3" />
                            </button>
                          )}
                          {prices && (
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
                                  </span>
                                  <span className="tabular-nums">
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

            {have.length > 0 && (
              <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                <House className="h-3.5 w-3.5" /> En casa:
                {have.map((item) => (
                  <button
                    key={item.name}
                    onClick={() => mark(item.name, { at_home: null })}
                    title="Deshacer: volver a preguntar"
                    className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 hover:bg-accent hover:text-foreground"
                  >
                    {item.name} <Undo2 className="h-3 w-3" />
                  </button>
                ))}
              </div>
            )}
            <ProductPicker key={picking?.name} item={picking} onOpenChange={(o) => o || setPicking(null)} onSaved={reload} />
          </>
        )
      )}
    </>
  )
}
