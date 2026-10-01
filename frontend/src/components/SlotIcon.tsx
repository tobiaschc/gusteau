import { Coffee, Moon, Salad, Utensils } from "lucide-react"
import { cn } from "@/lib/utils"

const STYLES: Record<string, { icon: typeof Coffee; cls: string }> = {
  // the ratatouille's vegetables: yellow squash, courgette, aubergine
  desayuno: { icon: Coffee, cls: "bg-amber-200/60 text-amber-800 dark:bg-amber-400/15 dark:text-amber-300" },
  comida: { icon: Salad, cls: "bg-lime-200/60 text-lime-800 dark:bg-lime-400/15 dark:text-lime-300" },
  cena: { icon: Moon, cls: "bg-purple-200/60 text-purple-800 dark:bg-purple-400/15 dark:text-purple-300" },
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
