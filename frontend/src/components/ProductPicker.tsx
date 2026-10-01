import { Ban, Check, ExternalLink, Loader2, Search } from "lucide-react"
import { useEffect, useState } from "react"
import { Dialog, DialogContent } from "@/components/ui/Dialog"
import { Input } from "@/components/ui/Input"
import { api, type Product, type ShoppingItem } from "@/lib/api"
import { cap, cn } from "@/lib/utils"

export const euro = (n: number) => n.toLocaleString("es-ES", { style: "currency", currency: "EUR" })

export function packLabel(p: Product): string {
  if (!p.size) return p.packaging ?? ""
  const size =
    p.size_format === "ud"
      ? `${p.size} ud`
      : p.size < 1
        ? `${Math.round(p.size * 1000)} ${p.size_format === "kg" ? "g" : "ml"}`
        : `${p.size.toLocaleString("es-ES")} ${p.size_format}`
  return `${p.approx ? "~" : ""}${size}${p.units && p.units > 1 ? ` · ${p.units} uds` : ""}`
}

/** Pick which Mercadona product an ingredient maps to (or mark it as not sold there). */
export function ProductPicker({
  item,
  onOpenChange,
  onSaved,
}: {
  item: ShoppingItem | null
  onOpenChange: (open: boolean) => void
  onSaved: () => void
}) {
  const [q, setQ] = useState(item?.name ?? "")
  const [results, setResults] = useState<Product[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const needle = q.trim()
    if (!item || needle.length < 2) return
    let stale = false
    const t = setTimeout(() => {
      setResults(null)
      setError(null)
      api
        .searchProducts(needle)
        .then((r) => stale || setResults(r))
        .catch((e) => stale || setError(e.message))
    }, 300)
    return () => {
      stale = true
      clearTimeout(t)
    }
  }, [q, item])

  const pick = async (id: string | null) => {
    if (!item) return
    setSaving(true)
    try {
      await api.setProduct(item.name, id)
      onSaved()
      onOpenChange(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const current = item?.mercadona?.product.id

  return (
    <Dialog open={!!item} onOpenChange={onOpenChange}>
      <DialogContent
        title={item ? cap(item.name) : ""}
        description="Elige el producto de Mercadona que compras para este ingrediente"
      >
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input autoFocus placeholder="Buscar en Mercadona" className="pl-9" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="-mx-2 max-h-[50dvh] space-y-0.5 overflow-y-auto px-2">
          {error && <p className="py-6 text-center text-sm text-red-500">{error}</p>}
          {!results && !error && (
            <div className="flex justify-center py-6">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          )}
          {results?.map((p) => (
            <div key={p.id} className="flex items-center gap-1">
              <button
                disabled={saving}
                onClick={() => pick(p.id)}
                className={cn(
                  "flex min-w-0 flex-1 items-center gap-3 rounded-md px-2 py-2 text-left transition-colors hover:bg-accent",
                  !p.available && "opacity-50",
                )}
              >
                {p.thumbnail ? (
                  <img src={`${p.thumbnail}?fit=crop&h=80&w=80`} alt="" className="h-10 w-10 shrink-0 rounded-md bg-white object-contain" />
                ) : (
                  <div className="h-10 w-10 shrink-0 rounded-md bg-secondary" />
                )}
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{p.name}</div>
                  <div className="truncate text-xs text-muted-foreground">
                    {[packLabel(p), euro(p.price), !p.available && "no disponible"].filter(Boolean).join(" · ")}
                  </div>
                </div>
                {current === p.id && <Check className="h-4 w-4 shrink-0 text-brand" />}
              </button>
              <a
                href={p.url}
                target="_blank"
                rel="noreferrer"
                className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                title="Ver en Mercadona"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            </div>
          ))}
          {results?.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">Sin resultados</p>}
        </div>
        <button
          disabled={saving}
          onClick={() => pick(null)}
          className="flex items-center justify-center gap-2 rounded-md py-2 text-sm text-muted-foreground transition-colors hover:bg-accent"
        >
          <Ban className="h-4 w-4" /> No lo compro en Mercadona
        </button>
      </DialogContent>
    </Dialog>
  )
}
