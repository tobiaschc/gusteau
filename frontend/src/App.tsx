import { Route, Routes } from "react-router-dom"
import { Layout } from "@/components/Layout"
import { AppProvider } from "@/lib/context"
import { EditorPage } from "@/pages/EditorPage"
import { NotFoundPage } from "@/pages/NotFoundPage"
import { PlanPage } from "@/pages/PlanPage"
import { RecipePage } from "@/pages/RecipePage"
import { RecipesPage } from "@/pages/RecipesPage"
import { StatsPage } from "@/pages/StatsPage"
import { ShoppingPage } from "@/pages/ShoppingPage"

export default function App() {
  return (
    <AppProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<PlanPage />} />
          <Route path="recipes" element={<RecipesPage />} />
          <Route path="recipes/new" element={<EditorPage />} />
          <Route path="recipes/:slug" element={<RecipePage />} />
          <Route path="recipes/:slug/edit" element={<EditorPage />} />
          <Route path="list" element={<ShoppingPage />} />
          <Route path="stats" element={<StatsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </AppProvider>
  )
}
