import { Coffee, Moon, Salad, Utensils } from "lucide-react"
import { cn } from "@/lib/utils"

const STYLES: Record<string, { icon: typeof Coffee; cls: string }> = {
  desayuno: { icon: Coffee, cls: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400" },
  comida: { icon: Salad, cls: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400" },
  cena: { icon: Moon, cls: "bg-indigo-100 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-400" },
}

export function slotOf(tags: string[]): string | null {
  return ["desayuno", "comida", "cena"].find((s) => tags.includes(s)) ?? null
}

export function SlotIcon({ slot, className }: { slot: string | null; className?: string }) {
  const style = (slot && STYLES[slot]) || { icon: Utensils, cls: "bg-secondary text-muted-foreground" }
  const Icon = style.icon
  return (
    <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg", style.cls, className)}>
      <Icon className="h-[18px] w-[18px]" />
    </div>
  )
}
