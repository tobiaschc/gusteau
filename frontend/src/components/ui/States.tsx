import { ChefHat, Loader2 } from "lucide-react"
import { useState } from "react"
import { loadingLine } from "@/components/Brand"
import { cn } from "@/lib/utils"

export function Loading({ label }: { label?: string }) {
  const [line] = useState(() => label ?? loadingLine())
  return (
    <div role="status" className="flex flex-col items-center gap-3 py-20 text-muted-foreground">
      <Loader2 className="h-6 w-6 animate-spin text-brand" />
      <p className="font-serif text-sm italic">{line}</p>
    </div>
  )
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm text-red-700 dark:text-red-400">
      <p className="font-medium">¡Algo se ha quemado en la cocina!</p>
      <p className="mt-1 opacity-90">
        {message}
        {onRetry && (
          <button className="ml-2 font-medium underline underline-offset-2" onClick={onRetry}>
            Reintentar
          </button>
        )}
      </p>
    </div>
  )
}

/** Friendly empty state used across pages. */
export function EmptyState({
  icon: Icon = ChefHat,
  title,
  children,
  action,
  className,
}: {
  icon?: typeof ChefHat
  title: string
  children?: React.ReactNode
  action?: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex flex-col items-center gap-3 rounded-xl border border-dashed bg-cream/60 px-6 py-10 text-center", className)}>
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand/10 text-brand">
        <Icon className="h-6 w-6" />
      </div>
      <h2 className="font-serif text-lg font-semibold">{title}</h2>
      {children && <p className="max-w-sm text-sm text-muted-foreground">{children}</p>}
      {action}
    </div>
  )
}

export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: string; children?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="font-serif text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  )
}
