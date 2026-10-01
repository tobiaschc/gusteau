import { ChevronLeft, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/Button"
import { useApp } from "@/lib/context"
import { isoWeek, shiftWeek, weekRange } from "@/lib/utils"

export function WeekNav() {
  const { week, setWeek } = useApp()
  const current = week === isoWeek()
  return (
    <div className="flex items-center gap-1 rounded-md border bg-background p-1">
      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setWeek(shiftWeek(week, -1))} aria-label="Semana anterior">
        <ChevronLeft />
      </Button>
      <button
        className="min-w-[8.5rem] px-1 text-center text-sm font-medium tabular-nums"
        onClick={() => setWeek(isoWeek())}
        title="Ir a esta semana"
      >
        {weekRange(week)}
        {!current && <span className="ml-1 text-muted-foreground">·</span>}
      </button>
      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setWeek(shiftWeek(week, 1))} aria-label="Semana siguiente">
        <ChevronRight />
      </Button>
    </div>
  )
}
