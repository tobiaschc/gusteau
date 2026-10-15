import { Heart } from "lucide-react"
import { Card } from "@/components/ui/Card"
import { ErrorBox, Loading, PageHeader } from "@/components/ui/States"
import { api } from "@/lib/api"
import { FAVORITE_CATEGORIES } from "@/lib/favoriteCategories"
import { useLoad } from "@/lib/hooks"
import { cn } from "@/lib/utils"

export function SettingsPage() {
  const { data: settings, error, loading, reload, setData } = useLoad(() => api.settings(), [])

  async function toggle(matches: string[]) {
    if (!settings) return
    const has = matches.every((m) => settings.favorite_ingredients.includes(m))
    const favorite_ingredients = has
      ? settings.favorite_ingredients.filter((f) => !matches.includes(f))
      : [...new Set([...settings.favorite_ingredients, ...matches])]
    setData(await api.saveSettings({ favorite_ingredients }))
  }

  return (
    <>
      <PageHeader title="Ajustes" />
      {error && <ErrorBox message={error} onRetry={reload} />}
      {loading && !settings ? (
        <Loading />
      ) : (
        settings && (
          <Card className="max-w-xl space-y-5 p-5">
            <div>
              <div className="mb-1 flex items-center gap-2">
                <Heart className="h-4 w-4 text-brand" />
                <h2 className="font-serif text-lg font-semibold">Ingredientes favoritos</h2>
              </div>
              <p className="text-sm text-muted-foreground">
                El plan semanal propondrá más a menudo recetas que los lleven.
              </p>
            </div>
            {FAVORITE_CATEGORIES.map(({ name, groups }) => (
              <div key={name}>
                <p className="mb-2 text-xs font-medium text-muted-foreground">{name}</p>
                <div className="flex flex-wrap gap-1.5">
                  {groups.map(({ label, matches }) => {
                    const active = matches.every((m) => settings.favorite_ingredients.includes(m))
                    return (
                      <button
                        key={label}
                        onClick={() => toggle(matches)}
                        className={cn(
                          "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                          active
                            ? "border-transparent bg-primary text-primary-foreground"
                            : "text-muted-foreground hover:bg-accent",
                        )}
                      >
                        {label}
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
          </Card>
        )
      )}
    </>
  )
}
