import { useState } from "react"
import { Button } from "@/components/ui/Button"
import { Dialog, DialogContent } from "@/components/ui/Dialog"
import type { Settings } from "@/lib/api"
import { api } from "@/lib/api"
import { FAVORITE_CATEGORIES } from "@/lib/favoriteCategories"
import { cn } from "@/lib/utils"

const SKIP_KEY = "gusteau-onboarding-skipped"

/** First-run wizard: ask which proteins/carbs/veggies/fruit the household likes, step by step
 * (the classic "plato saludable" categories), to seed Settings.favorite_ingredients. Shown
 * until at least one favorite is saved or skipped. */
export function FavoritesOnboarding({ settings, onSaved }: { settings: Settings; onSaved: (s: Settings) => void }) {
  const [skipped, setSkipped] = useState(() => localStorage.getItem(SKIP_KEY) === "1")
  const [step, setStep] = useState(0)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [saving, setSaving] = useState(false)

  if (settings.favorite_ingredients.length > 0 || skipped) return null

  const last = step === FAVORITE_CATEGORIES.length - 1
  const { name, groups } = FAVORITE_CATEGORIES[step]

  function toggle(label: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(label)) next.delete(label)
      else next.add(label)
      return next
    })
  }

  function skip() {
    localStorage.setItem(SKIP_KEY, "1")
    setSkipped(true)
  }

  async function finish() {
    setSaving(true)
    try {
      const allGroups = FAVORITE_CATEGORIES.flatMap((c) => c.groups)
      const favorite_ingredients = allGroups.filter((g) => selected.has(g.label)).flatMap((g) => g.matches)
      onSaved(await api.saveSettings({ favorite_ingredients }))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && skip()}>
      <DialogContent title="¿Qué te gusta comer?" description={`Paso ${step + 1} de ${FAVORITE_CATEGORIES.length} — ${name}`}>
        <p className="text-sm text-muted-foreground">
          El plan semanal propondrá más a menudo recetas con lo que marques aquí. Puedes cambiarlo luego en Ajustes.
        </p>
        <div className="flex flex-wrap gap-2">
          {groups.map(({ label }) => (
            <button
              key={label}
              onClick={() => toggle(label)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-sm font-medium transition-colors",
                selected.has(label) ? "border-brand bg-brand/10 text-foreground" : "text-muted-foreground hover:bg-accent",
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex items-center justify-between gap-2">
          <button className="text-xs text-muted-foreground underline-offset-2 hover:underline" onClick={skip}>
            Ahora no
          </button>
          <div className="flex gap-2">
            {step > 0 && (
              <Button variant="ghost" onClick={() => setStep(step - 1)}>
                Atrás
              </Button>
            )}
            {last ? (
              <Button onClick={finish} disabled={saving}>
                Terminar
              </Button>
            ) : (
              <Button onClick={() => setStep(step + 1)}>Siguiente</Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
