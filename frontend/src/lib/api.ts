// Types are generated from the backend's OpenAPI schema: `npm run gen:api` (see gusteau/api/openapi.py).
import type { components } from "./api.gen"

type S = components["schemas"]
export type RecipeSummary = S["RecipeSummary"]
export type Recipe = S["RecipeDetail"]
export type Segment = Recipe["steps"][number][number]
export type Plan = S["Plan"]
export type Product = S["Product"]
export type PricedItem = S["PricedItem"]
export type ShoppingItem = S["ShoppingItem"]
export type Shopping = S["Shopping"]
export type Settings = S["Settings"]
export type MealOutcome = S["MealOutcome"]
export type Purchase = S["Purchase"]

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
  setOutcome: (week: string, day: string, slot: string, o: S["OutcomeIn"]) =>
    request<Plan>(`/plans/${week}/meals/${day}/${slot}/outcome`, json("PUT", o)),
  purchases: (week?: string) => request<Purchase[]>(`/purchases${week ? `?week=${week}` : ""}`),
  createPurchase: (week: string, people?: number) =>
    request<Purchase>(`/plans/${week}/purchases${people ? `?people=${people}` : ""}`, { method: "POST" }),
  updatePurchase: (id: number, actual_total: number | null) =>
    request<Purchase>(`/purchases/${id}`, json("PATCH", { actual_total })),
  deletePurchase: (id: number) => request<void>(`/purchases/${id}`, { method: "DELETE" }),
  settings: () => request<Settings>("/settings"),
  saveSettings: (s: S["SettingsIn"]) => request<Settings>("/settings", json("PUT", s)),
  searchProducts: (q: string) => request<Product[]>(`/products/search?q=${encodeURIComponent(q)}`),
  setProduct: (ingredient: string, id: string | null) =>
    request<S["ProductPick"]>(`/products/${encodeURIComponent(ingredient)}`, json("PUT", { id })),
}
