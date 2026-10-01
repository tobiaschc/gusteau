import { Receipt, Trash2 } from "lucide-react"
import { useState } from "react"
import { euro } from "@/components/ProductPicker"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { api, type Purchase } from "@/lib/api"
import { useLoad } from "@/lib/hooks"

/** "Compra hecha": freezes the list with today's prices; optionally the receipt total. */
export function PurchaseBar({ week, people }: { week: string; people: number }) {
  const purchases = useLoad(() => api.purchases(week), [week])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
      purchases.reload()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const list = purchases.data ?? []
  return (
    <div className="mb-4 space-y-2">
      {list.map((p) => (
        <PurchaseRow
          key={p.id}
          purchase={p}
          busy={busy}
          onReceipt={(v) => run(() => api.updatePurchase(p.id, v))}
          onDelete={() => run(() => api.deletePurchase(p.id))}
        />
      ))}
      {list.length === 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-dashed px-3 py-2 text-sm text-muted-foreground">
          <span className="flex-1">¿Ya has hecho la compra? Guárdala para ver el gasto en Estadísticas.</span>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => run(() => api.createPurchase(week, people))}>
            <Receipt /> Compra hecha
          </Button>
        </div>
      )}
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  )
}

function PurchaseRow({
  purchase: p,
  busy,
  onReceipt,
  onDelete,
}: {
  purchase: Purchase
  busy: boolean
  onReceipt: (v: number | null) => void
  onDelete: () => void
}) {
  const [value, setValue] = useState(p.actual_total?.toString().replace(".", ",") ?? "")
  const parsed = value.trim() ? Number(value.replace(",", ".")) : null
  const valid = parsed === null || (Number.isFinite(parsed) && parsed >= 0)
  const changed = parsed !== p.actual_total
  const date = new Date(p.created_at).toLocaleDateString("es-ES", { day: "numeric", month: "short" })

  return (
    <div className="flex items-center gap-3 rounded-lg border bg-card px-3 py-2 text-sm">
      <Receipt className="h-4 w-4 shrink-0 text-brand" />
      <div className="min-w-0 flex-1 leading-tight">
        <div className="truncate font-medium">Compra · {date}</div>
        {p.estimated_total !== null && (
          <div className="text-xs text-muted-foreground">~{euro(p.estimated_total)} estimado</div>
        )}
      </div>
      <form
        className="flex items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (valid && changed) onReceipt(parsed)
        }}
      >
        <label className="text-xs text-muted-foreground" htmlFor={`ticket-${p.id}`}>
          Ticket
        </label>
        <Input
          id={`ticket-${p.id}`}
          inputMode="decimal"
          placeholder="€"
          className="h-8 w-20 text-right tabular-nums"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        {changed && (
          <Button size="sm" type="submit" disabled={busy || !valid}>
            Guardar
          </Button>
        )}
      </form>
      <Button size="sm" variant="ghost" aria-label="Borrar compra" disabled={busy} onClick={onDelete}>
        <Trash2 />
      </Button>
    </div>
  )
}
