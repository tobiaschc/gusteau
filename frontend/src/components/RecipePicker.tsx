import { Check, Search, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"
import { SlotIcon, slotOf } from "@/components/SlotIcon"
import { Dialog, DialogContent } from "@/components/ui/Dialog"
import { Input } from "@/components/ui/Input"
import type { RecipeSummary } from "@/lib/api"
import { cn, SLOT_LABELS } from "@/lib/utils"

export function RecipePicker({
  open,
  onOpenChange,
  recipes,
  slot,
  current,
  title,
  onPick,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  recipes: RecipeSummary[]
  slot: string
  current: string | null
  title: string
  onPick: (slug: string | null) => void
}) {
  const [q, setQ] = useState("")
  const list = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return recipes
      .filter((r) => !needle || r.title.toLowerCase().includes(needle) || r.ingredients.some((i) => i.includes(needle)))
      .toSorted((a, b) => Number(b.tags.includes(slot)) - Number(a.tags.includes(slot)) || a.title.localeCompare(b.title))
  }, [recipes, q, slot])

  return (
    <Dialog open={open} onOpenChange={(o) => (onOpenChange(o), o || setQ(""))}>
      <DialogContent title={title} description={`Elige una receta para ${SLOT_LABELS[slot]?.toLowerCase() ?? slot}`}>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input autoFocus placeholder="Buscar por nombre o ingrediente" className="pl-9" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="-mx-2 max-h-[50dvh] space-y-0.5 overflow-y-auto px-2">
          {list.map((r) => {
            const fits = r.tags.includes(slot)
            return (
              <button
                key={r.slug}
                onClick={() => onPick(r.slug)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-md px-2 py-2 text-left transition-colors hover:bg-accent",
                  !fits && "opacity-60",
                )}
              >
                <SlotIcon slot={slotOf(r.tags)} className="h-8 w-8" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{r.title}</div>
                  <div className="truncate text-xs text-muted-foreground">
                    {[r.time, r.tags.join(" · ")].filter(Boolean).join(" · ")}
                  </div>
                </div>
                {current === r.slug && <Check className="h-4 w-4 text-brand" />}
              </button>
            )
          })}
          {list.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">Sin resultados</p>}
        </div>
        {current && (
          <button
            onClick={() => onPick(null)}
            className="flex items-center justify-center gap-2 rounded-md py-2 text-sm text-red-500 transition-colors hover:bg-red-50 dark:hover:bg-red-900/20"
          >
            <Trash2 className="h-4 w-4" /> Dejar vacío
          </button>
        )}
      </DialogContent>
    </Dialog>
  )
}
