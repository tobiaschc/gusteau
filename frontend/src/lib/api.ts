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
export type Stats = S["Stats"]

/** The HTTP API, or the backend running inside the app (mobile build) — same paths, same Responses. */
export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  if (import.meta.env.VITE_RUNTIME === "pyodide") {
    const { pyFetch } = await import("./pyodide/client") // statically dropped from the web build
    return pyFetch(`/api${path}`, init)
  }
  return fetch(`/api${path}`, init)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(path, {
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
  mark: (week: string, ingredient: string, m: S["MarkIn"]) =>
    request<S["Mark"]>(`/plans/${week}/shopping/${encodeURIComponent(ingredient)}`, json("PATCH", m)),
  clearCart: (week: string) => request<void>(`/plans/${week}/shopping/cart`, { method: "DELETE" }),
  setOutcome: (week: string, day: string, slot: string, o: S["OutcomeIn"]) =>
    request<Plan>(`/plans/${week}/meals/${day}/${slot}/outcome`, json("PUT", o)),
  purchases: (week?: string) => request<Purchase[]>(`/purchases${week ? `?week=${week}` : ""}`),
  createPurchase: (week: string, people?: number) =>
    request<Purchase>(`/plans/${week}/purchases${people ? `?people=${people}` : ""}`, { method: "POST" }),
  updatePurchase: (id: number, actual_total: number | null) =>
    request<Purchase>(`/purchases/${id}`, json("PATCH", { actual_total })),
  deletePurchase: (id: number) => request<void>(`/purchases/${id}`, { method: "DELETE" }),
  stats: (weeks: number) => request<Stats>(`/stats?weeks=${weeks}`),
  settings: () => request<Settings>("/settings"),
  saveSettings: (s: S["SettingsIn"]) => request<Settings>("/settings", json("PUT", s)),
  searchProducts: (q: string) => request<Product[]>(`/products/search?q=${encodeURIComponent(q)}`),
  setProduct: (ingredient: string, id: string | null) =>
    request<S["ProductPick"]>(`/products/${encodeURIComponent(ingredient)}`, json("PUT", { id })),
}
