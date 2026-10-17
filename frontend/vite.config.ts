import path from "node:path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// `--mode mobile` (.env.mobile): the backend runs in-app under Pyodide, so the build is a standalone SPA in dist/,
// served with public-mobile/ (public/ + the Pyodide assets from scripts/build_pyodide.py).
// BASE_PATH overrides the base URL for a mobile build served from a subpath (e.g. GitHub Pages project sites).
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  ...(mode === "mobile"
    ? { base: process.env.BASE_PATH ?? "/", publicDir: "public-mobile", build: { outDir: "dist", emptyOutDir: true } }
    : { build: { outDir: "../gusteau/static", emptyOutDir: true } }),
  worker: { format: "es" as const }, // the Pyodide worker is code-split
  optimizeDeps: { exclude: ["pyodide"] },
  server: { proxy: { "/api": "http://localhost:8000" } },
}))
