import { Check, Repeat, X } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/Button"
import { Dialog, DialogContent } from "@/components/ui/Dialog"
import { Input } from "@/components/ui/Input"
import type { MealOutcome, RecipeSummary } from "@/lib/api"
import { cn } from "@/lib/utils"

type Choice = "cooked" | "skipped" | "swapped"

/** What actually happened to a past meal: cooked as planned (default), skipped, or something else. */
export function OutcomeDialog({
  title,
  planned,
  outcome,
  recipes,
  onSave,
  onClose,
  onChangePlan,
}: {
  title: string
  planned: string
  outcome?: MealOutcome
  recipes: RecipeSummary[]
  onSave: (o: { status: Choice; swap_slug?: string | null; swap_title?: string | null }) => Promise<void>
  onClose: () => void
  onChangePlan: () => void
}) {
  const [status, setStatus] = useState<Choice>(outcome?.status ?? "cooked")
  const [query, setQuery] = useState(outcome?.swap_slug ? "" : (outcome?.swap_title ?? ""))
  const [slug, setSlug] = useState<string | null>(outcome?.swap_slug ?? null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const matches = query.trim()
    ? recipes.filter((r) => r.title.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 5)
    : []
  const canSave = status !== "swapped" || slug || query.trim()

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      await onSave(
        status === "swapped" ? { status, swap_slug: slug, swap_title: slug ? null : query.trim() } : { status },
      )
      onClose()
    } catch (e) {
      setError((e as Error).message)
      setSaving(false)
    }
  }

  const options: { id: Choice; label: string; icon: typeof Check }[] = [
    { id: "cooked", label: "Se cocinó", icon: Check },
    { id: "swapped", label: "Otra cosa", icon: Repeat },
    { id: "skipped", label: "No se hizo", icon: X },
  ]

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={title} description={planned}>
        <div className="grid grid-cols-3 gap-2">
          {options.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setStatus(id)}
              className={cn(
                "flex flex-col items-center gap-1.5 rounded-lg border p-3 text-center text-xs font-medium transition-colors",
                status === id ? "border-brand bg-brand/10 text-foreground" : "text-muted-foreground hover:bg-accent",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>
        {status === "swapped" && (
          <div className="space-y-2">
            <Input
              autoFocus
              placeholder="Receta o, por ejemplo, «pizza fuera»"
              value={slug ? (recipes.find((r) => r.slug === slug)?.title ?? query) : query}
              onChange={(e) => {
                setSlug(null)
                setQuery(e.target.value)
              }}
            />
            {!slug && matches.length > 0 && (
              <ul className="rounded-lg border">
                {matches.map((r) => (
                  <li key={r.slug}>
                    <button
                      className="w-full px-3 py-2 text-left text-sm hover:bg-accent"
                      onClick={() => {
                        setSlug(r.slug)
                        setQuery(r.title)
                      }}
                    >
                      {r.title}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div className="flex items-center justify-end gap-2">
          <button className="mr-auto text-xs text-muted-foreground underline-offset-2 hover:underline" onClick={onChangePlan}>
            Cambiar el plan
          </button>
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={save} disabled={saving || !canSave}>
            Guardar
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
