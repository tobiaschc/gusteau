import { Clock, Plus, Search, SearchX } from "lucide-react"
import { useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { SlotIcon, slotOf } from "@/components/SlotIcon"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { Input } from "@/components/ui/Input"
import { EmptyState, ErrorBox, Loading, PageHeader } from "@/components/ui/States"
import { api } from "@/lib/api"
import { useLoad } from "@/lib/hooks"

const SLOT_ORDER = ["desayuno", "comida", "cena"]

export function RecipesPage() {
  const { data, error, loading, reload } = useLoad(() => api.recipes(), [])
  const [q, setQ] = useState("")
  const [tag, setTag] = useState<string | null>(null)

  const tags = useMemo(() => {
    const all = [...new Set((data ?? []).flatMap((r) => r.tags))]
    return all.toSorted((a, b) => {
      const ia = SLOT_ORDER.indexOf(a)
      const ib = SLOT_ORDER.indexOf(b)
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b)
    })
  }, [data])

  const list = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return (data ?? []).filter(
      (r) =>
        (!tag || r.tags.includes(tag)) &&
        (!needle || r.title.toLowerCase().includes(needle) || r.ingredients.some((i) => i.includes(needle))),
    )
  }, [data, q, tag])

  return (
    <>
      <PageHeader title="Recetas" subtitle={data ? `${data.length} recetas en el banco` : undefined}>
        <Link to="/recipes/new">
          <Button>
            <Plus /> Nueva receta
          </Button>
        </Link>
      </PageHeader>

      <div className="mb-6 space-y-3">
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Buscar por nombre o ingrediente" className="pl-9" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {tags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            <button onClick={() => setTag(null)}>
              <Badge active={!tag}>Todas</Badge>
            </button>
            {tags.map((t) => (
              <button key={t} onClick={() => setTag(tag === t ? null : t)}>
                <Badge active={tag === t} className="capitalize">
                  {t}
                </Badge>
              </button>
            ))}
          </div>
        )}
      </div>

      {error && <ErrorBox message={error} onRetry={reload} />}
      {loading && !data ? (
        <Loading />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {list.map((r) => (
            <Link key={r.slug} to={`/recipes/${r.slug}`}>
              <Card className="group h-full p-4 transition-all hover:-translate-y-0.5 hover:shadow-md">
                <div className="flex items-start gap-3">
                  <SlotIcon slot={slotOf(r.tags)} className="h-10 w-10" />
                  <div className="min-w-0 flex-1">
                    <h3 className="font-medium leading-snug">{r.title}</h3>
                    <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                      {r.time && (
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {r.time}
                        </span>
                      )}
                      <span>{r.ingredients.length} ingredientes</span>
                    </div>
                  </div>
                </div>
                <p className="mt-3 line-clamp-2 text-xs text-muted-foreground">{r.ingredients.join(", ")}</p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {r.tags.map((t) => (
                    <Badge key={t} className="capitalize">
                      {t}
                    </Badge>
                  ))}
                </div>
              </Card>
            </Link>
          ))}
          {list.length === 0 && data && (
            <EmptyState
              icon={SearchX}
              className="col-span-full"
              title={data.length ? "Ni Remy lo encuentra" : "El banco de recetas está vacío"}
              action={
                data.length ? (
                  <Button variant="outline" onClick={() => { setQ(""); setTag(null) }}>
                    Limpiar búsqueda
                  </Button>
                ) : (
                  <Link to="/recipes/new">
                    <Button variant="brand"><Plus /> Nueva receta</Button>
                  </Link>
                )
              }
            >
              {data.length
                ? "Ninguna receta coincide. Prueba con otro ingrediente: la imaginación es el único límite."
                : "Cualquiera puede cocinar: empieza por tu primera receta."}
            </EmptyState>
          )}
        </div>
      )}
    </>
  )
}
