import * as React from "react"
import { cn } from "@/lib/utils"

export function Badge({
  className,
  active,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { active?: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors",
        active ? "border-transparent bg-primary text-primary-foreground" : "bg-secondary/60 text-secondary-foreground",
        className,
      )}
      {...props}
    />
  )
}
