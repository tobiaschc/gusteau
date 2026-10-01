import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

export const DAY_LABELS: Record<string, string> = {
  lunes: "Lunes",
  martes: "Martes",
  miercoles: "Miércoles",
  jueves: "Jueves",
  viernes: "Viernes",
  sabado: "Sábado",
  domingo: "Domingo",
}

export const SLOT_LABELS: Record<string, string> = {
  desayuno: "Desayuno",
  comida: "Comida",
  cena: "Cena",
}

/** ISO week "YYYY-Www" for a date. */
export function isoWeek(date = new Date()): string {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()))
  const day = d.getUTCDay() || 7
  d.setUTCDate(d.getUTCDate() + 4 - day)
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1))
  const week = Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7)
  return `${d.getUTCFullYear()}-W${String(week).padStart(2, "0")}`
}

/** Monday of an ISO week. */
export function weekMonday(week: string): Date {
  const [y, w] = week.split("-W").map(Number)
  const jan4 = new Date(Date.UTC(y, 0, 4))
  const monday = new Date(jan4)
  monday.setUTCDate(jan4.getUTCDate() - ((jan4.getUTCDay() || 7) - 1) + (w - 1) * 7)
  return monday
}

export function shiftWeek(week: string, delta: number): string {
  const m = weekMonday(week)
  m.setUTCDate(m.getUTCDate() + delta * 7)
  return isoWeek(new Date(m.getUTCFullYear(), m.getUTCMonth(), m.getUTCDate()))
}

export function weekRange(week: string): string {
  const start = weekMonday(week)
  const end = new Date(start)
  end.setUTCDate(start.getUTCDate() + 6)
  const fmt = (d: Date) => d.toLocaleDateString("es-ES", { day: "numeric", month: "short", timeZone: "UTC" })
  return `${fmt(start)} – ${fmt(end)}`
}

export function formatQty(q: number | null, unit: string): string {
  if (q === null) return "al gusto"
  let v = q
  let u = unit
  if (u === "g" && v >= 1000) [v, u] = [v / 1000, "kg"]
  if (u === "ml" && v >= 1000) [v, u] = [v / 1000, "l"]
  const n = Number.isInteger(v) ? String(v) : v.toLocaleString("es-ES", { maximumFractionDigits: v < 10 ? 1 : 0 })
  return u ? `${n} ${u}` : n
}
