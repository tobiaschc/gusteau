import { useEffect, useState } from "react"
import { cn } from "@/lib/utils"

/** Original Gusteau mark: a chef's toque with a tiny tail peeking out (no third-party artwork). */
export function ToqueMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" aria-hidden="true" className={className}>
      <rect width="64" height="64" rx="14" fill="#94222e" />
      <path d="M43 47c5 0 8 2 8 5.5S48 57 45.5 55" fill="none" stroke="#e9c37a" strokeWidth="2.4" strokeLinecap="round" />
      <path
        d="M21 31.5a8.5 8.5 0 0 1 3.2-16.4A10 10 0 0 1 32 11a10 10 0 0 1 7.8 4.1 8.5 8.5 0 0 1 3.2 16.4V43H21z"
        fill="#fbf6ee"
      />
      <path d="M27 32v8M32 31v9M37 32v8" stroke="#94222e" strokeOpacity=".22" strokeWidth="1.6" strokeLinecap="round" />
      <rect x="19.5" y="43" width="25" height="7" rx="2" fill="#e9c37a" />
    </svg>
  )
}

export const QUOTES = [
  "Cualquiera puede cocinar.",
  "Un gran cocinero puede salir de cualquier parte.",
  "Si eres lo que comes, come solo lo mejor.",
  "Atrévete con lo que quizá no salga.",
  "Perspectiva, por favor: fresca y bien sazonada.",
]

export function RotatingQuote({ className }: { className?: string }) {
  const [i, setI] = useState(() => Math.floor(Date.now() / 86_400_000) % QUOTES.length)
  useEffect(() => {
    const id = setInterval(() => setI((n) => (n + 1) % QUOTES.length), 20_000)
    return () => clearInterval(id)
  }, [])
  return (
    <button
      type="button"
      title="Otra cita"
      onClick={() => setI((n) => (n + 1) % QUOTES.length)}
      className={cn("block text-left font-serif text-[13px] italic leading-snug text-muted-foreground transition-colors hover:text-foreground", className)}
    >
      “{QUOTES[i]}”
    </button>
  )
}

const LOADING = ["Remy está en ello…", "Calentando los fogones…", "Afilando los cuchillos…", "Probando la salsa…"]

export function loadingLine() {
  return LOADING[Math.floor(Math.random() * LOADING.length)]
}
