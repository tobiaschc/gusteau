import { CalendarDays } from "lucide-react"
import { Link } from "react-router-dom"
import { Button } from "@/components/ui/Button"
import { EmptyState } from "@/components/ui/States"

export function NotFoundPage() {
  return (
    <EmptyState
      title="Te has perdido por las cocinas"
      className="mx-auto mt-10 max-w-lg"
      action={
        <Link to="/">
          <Button variant="brand">
            <CalendarDays /> Volver al plan
          </Button>
        </Link>
      }
    >
      Esta página no existe. Ni siquiera en las alcantarillas de París.
    </EmptyState>
  )
}
