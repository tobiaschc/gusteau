import { ArrowLeft, Info, Save } from "lucide-react"
import { useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { ErrorBox, Loading, PageHeader } from "@/components/ui/States"
import { api } from "@/lib/api"

const TEMPLATE = `---
title: Nueva receta
servings: 1
tags: [comida]
time: 20 min
---
Sofríe @cebolla{50%g} con @aceite de oliva virgen extra{10%ml}.

Añade @tomate{2} y cocina ~{10%minutos}.
`

export function EditorPage() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const [source, setSource] = useState<string | null>(slug ? null : TEMPLATE)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (slug) api.recipe(slug).then((r) => setSource(r.source)).catch((e: Error) => setError(e.message))
  }, [slug])

  const save = async () => {
    if (source === null) return
    setSaving(true)
    setError(null)
    try {
      const r = slug ? await api.updateRecipe(slug, source) : await api.createRecipe(source)
      navigate(`/recipes/${r.slug}`)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link
        to={slug ? `/recipes/${slug}` : "/recipes"}
        className="mb-6 flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Volver
      </Link>
      <PageHeader title={slug ? "Editar receta" : "Nueva receta"}>
        <Button onClick={save} disabled={saving || source === null}>
          <Save /> Guardar
        </Button>
      </PageHeader>
      {error && <div className="mb-4"><ErrorBox message={error} /></div>}
      {source === null ? (
        <Loading />
      ) : (
        <textarea
          value={source}
          onChange={(e) => setSource(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "s") {
              e.preventDefault()
              save()
            }
          }}
          spellCheck={false}
          className="min-h-[24rem] w-full resize-y rounded-lg border border-input bg-background p-4 font-mono text-sm leading-relaxed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      )}
      <Card className="mt-4 flex gap-3 p-4 text-sm text-muted-foreground">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <div className="space-y-1">
          <p>
            Formato <a className="underline" href="https://cooklang.org/docs/spec/" target="_blank" rel="noreferrer">Cooklang</a>,
            cantidades para <code>servings</code> personas.
          </p>
          <p>
            <code>@ingrediente{"{150%g}"}</code> · <code>@huevos{"{2}"}</code> · <code>@sal</code> (al gusto) ·{" "}
            <code>#sartén{"{}"}</code> · <code>~{"{10%minutos}"}</code>. Una línea en blanco separa pasos.
          </p>
          <p>
            <code>tags</code> con <code>desayuno</code>, <code>comida</code> o <code>cena</code> decide en qué huecos del plan
            puede salir.
          </p>
          <p>
            Añade <code>habitual</code> a tus platos de cabecera para que el plan los proponga más a menudo, y{" "}
            <code>finde</code> a los largos para que solo salgan sábado o domingo.
          </p>
        </div>
      </Card>
    </div>
  )
}
