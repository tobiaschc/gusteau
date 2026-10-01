import { ArrowLeft, Clock, Pencil, SearchX, Sparkles, Trash2, Users } from "lucide-react"
import { useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { SlotIcon, slotOf } from "@/components/SlotIcon"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { Dialog, DialogContent } from "@/components/ui/Dialog"
import { EmptyState, ErrorBox, Loading } from "@/components/ui/States"
import { api, type Segment } from "@/lib/api"
import { useApp } from "@/lib/context"
import { useLoad } from "@/lib/hooks"
import { cap, formatQty } from "@/lib/utils"

function Step({ segments, scale }: { segments: Segment[]; scale: number }) {
  return (
    <p className="leading-relaxed">
      {segments.map((s, i) => {
        if (s.type === "text") return <span key={i}>{s.value}</span>
        if (s.type === "ingredient")
          return (
            <span key={i} className="font-medium text-brand" title={s.quantity !== null ? formatQty(s.quantity * scale, s.unit) : undefined}>
              {s.name}
            </span>
          )
        if (s.type === "cookware") return <span key={i} className="font-medium">{s.name}</span>
        return (
          <span key={i} className="font-medium">
            {s.quantity !== null ? formatQty(s.quantity, s.unit) : s.name}
          </span>
        )
      })}
    </p>
  )
}

export function RecipePage() {
  const { slug = "" } = useParams()
  const navigate = useNavigate()
  const { people } = useApp()
  const { data: r, error, loading, reload } = useLoad(() => api.recipe(slug), [slug])
  const [confirm, setConfirm] = useState(false)
  const [delError, setDelError] = useState<string | null>(null)
  const [checked, setChecked] = useState<Set<number>>(new Set())

  if (loading && !r) return <Loading />
  if (error && /no encontrad|not found|404/i.test(error))
    return (
      <EmptyState
        icon={SearchX}
        title="Esta receta no está en la carta"
        action={
          <Link to="/recipes">
            <Button variant="outline">
              <ArrowLeft /> Volver a las recetas
            </Button>
          </Link>
        }
      >
        Quizá alguien la retiró del menú. Hasta los mejores cocineros pierden alguna receta.
      </EmptyState>
    )
  if (error || !r) return <ErrorBox message={error ?? "No encontrada"} onRetry={reload} />

  // Easter egg: the dish that won over the toughest critic in Paris.
  const isRatatouille = /ratatouille|byaldi/i.test(`${slug} ${r.title}`)

  const scale = people / r.servings
  // Same ingredient used in several steps (e.g. oil) -> one line with the total.
  const ingredients = r.ingredients.reduce<typeof r.ingredients>((acc, ing) => {
    const prev = acc.find((x) => x.name === ing.name && x.unit === ing.unit)
    if (prev && prev.quantity !== null && ing.quantity !== null) prev.quantity += ing.quantity
    else if (!prev) acc.push({ ...ing })
    return acc
  }, [])
  const remove = async () => {
    try {
      await api.deleteRecipe(slug)
      navigate("/recipes")
    } catch (e) {
      setDelError((e as Error).message)
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6 flex items-center justify-between">
        <Link to="/recipes" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Recetas
        </Link>
        <div className="flex gap-2">
          <Link to={`/recipes/${slug}/edit`}>
            <Button variant="outline" size="sm">
              <Pencil /> Editar
            </Button>
          </Link>
          <Button variant="ghost" size="sm" className="text-red-500 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/20" onClick={() => setConfirm(true)}>
            <Trash2 />
          </Button>
        </div>
      </div>

      <div className="mb-8 flex items-start gap-4">
        <SlotIcon slot={slotOf(r.tags)} className="h-12 w-12 rounded-xl" />
        <div>
          <h1 className="font-serif text-2xl font-semibold tracking-tight sm:text-3xl">{r.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            {r.time && (
              <span className="flex items-center gap-1">
                <Clock className="h-4 w-4" /> {r.time}
              </span>
            )}
            <span className="flex items-center gap-1">
              <Users className="h-4 w-4" /> {people} {people === 1 ? "persona" : "personas"}
            </span>
            {r.tags.map((t) => (
              <Badge key={t} className="capitalize">
                {t}
              </Badge>
            ))}
          </div>
        </div>
      </div>

      {isRatatouille && (
        <div className="mb-8 flex items-start gap-3 rounded-xl border border-gold/40 bg-cream px-4 py-3 text-cream-foreground">
          <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-gold" />
          <p className="font-serif text-sm italic leading-relaxed">
            El plato que hizo sonreír al crítico más temido de París. Sírvelo despacio: sabe a infancia.
          </p>
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Card className="h-fit p-5">
          <h2 className="mb-3 font-serif text-lg font-semibold">Ingredientes</h2>
          <ul className="space-y-1">
            {ingredients.map((ing, i) => (
              <li key={i}>
                <label className="flex cursor-pointer items-baseline gap-3 rounded-md px-1 py-1 hover:bg-accent/60">
                  <input
                    type="checkbox"
                    className="translate-y-0.5 accent-[hsl(var(--brand))]"
                    checked={checked.has(i)}
                    onChange={() => {
                      const next = new Set(checked)
                      if (next.has(i)) next.delete(i)
                      else next.add(i)
                      setChecked(next)
                    }}
                  />
                  <span className={checked.has(i) ? "text-muted-foreground line-through" : ""}>
                    <span>{cap(ing.name)}</span>
                    <span className="ml-1.5 text-sm text-muted-foreground tabular-nums">
                      {ing.quantity === null ? "al gusto" : formatQty(ing.quantity * scale, ing.unit || (ing.quantity * scale === 1 ? "ud" : "uds"))}
                    </span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </Card>
        <div>
          <h2 className="mb-3 font-serif text-lg font-semibold">Preparación</h2>
          <ol className="space-y-4">
            {r.steps.map((s, i) => (
              <li key={i} className="flex gap-4">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand/10 font-serif text-sm font-semibold text-brand">
                  {i + 1}
                </span>
                <div className="pt-0.5">
                  <Step segments={s} scale={scale} />
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <Dialog open={confirm} onOpenChange={setConfirm}>
        <DialogContent title="¿Borrar receta?" description={`Se eliminará "${r.title}" del banco. Los planes que la usen quedarán con el hueco vacío.`}>
          {delError && <ErrorBox message={delError} />}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setConfirm(false)}>
              Cancelar
            </Button>
            <Button variant="destructive" onClick={remove}>
              Borrar
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
