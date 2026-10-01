export type RecipeSummary = {
  slug: string
  title: string
  tags: string[]
  time: string | null
  servings: number
  ingredients: string[]
}

export type Segment =
  | { type: "text"; value: string }
  | { type: "ingredient"; name: string; quantity: number | null; unit: string }
  | { type: "cookware"; name: string }
  | { type: "timer"; name: string; quantity: number | null; unit: string }

export type Recipe = Omit<RecipeSummary, "ingredients"> & {
  ingredients: { name: string; quantity: number | null; unit: string }[]
  steps: Segment[][]
  source: string
}

export type Plan = {
  week: string
  days: Record<string, Record<string, string | null>>
  titles: Record<string, string>
}

export type Product = {
  id: string
  name: string
  price: number
  size: number | null
  size_format: string
  units: number | null
  approx: boolean
  available: boolean
  url: string
  thumbnail: string | null
  packaging: string | null
}

export type PricedItem = { product: Product; packs: number; cost: number; approx: boolean; pantry: boolean; auto: boolean }

export type ShoppingItem = {
  name: string
  aisle: string
  recipes: string[]
  amounts: { unit: string; quantity: number; label: string }[]
  mercadona: PricedItem | null
}

export type Shopping = {
  week: string
  people: number
  meals: number
  items: ShoppingItem[]
  total: number | null
  prices_error: string | null
}
export type Settings = { people: number; slots: string[]; prices: boolean; warehouse: string }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = typeof body.detail === "string" ? body.detail : `Error ${res.status}`
    throw new Error(detail)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) })

export const api = {
  recipes: () => request<RecipeSummary[]>("/recipes"),
  recipe: (slug: string) => request<Recipe>(`/recipes/${slug}`),
  createRecipe: (source: string) => request<Recipe>("/recipes", json("POST", { source })),
  updateRecipe: (slug: string, source: string) => request<Recipe>(`/recipes/${slug}`, json("PUT", { source })),
  deleteRecipe: (slug: string) => request<void>(`/recipes/${slug}`, { method: "DELETE" }),
  plan: (week: string) => request<Plan>(`/plans/${week}`),
  savePlan: (week: string, days: Plan["days"]) => request<Plan>(`/plans/${week}`, json("PUT", { days })),
  generate: (week: string, keep: boolean) => request<Plan>(`/plans/${week}/generate`, json("POST", { keep })),
  shopping: (week: string, people?: number) =>
    request<Shopping>(`/plans/${week}/shopping${people ? `?people=${people}` : ""}`),
  settings: () => request<Settings>("/settings"),
  saveSettings: (s: Partial<Settings>) => request<Settings>("/settings", json("PUT", s)),
  searchProducts: (q: string) => request<Product[]>(`/products/search?q=${encodeURIComponent(q)}`),
  setProduct: (ingredient: string, id: string | null) =>
    request<{ ingredient: string; id: string | null }>(`/products/${encodeURIComponent(ingredient)}`, json("PUT", { id })),
}
