<p align="center">
  <img src="docs/logo.svg" width="96" height="96" alt="Gusteau logo: a chef's toque">
</p>

<h1 align="center">Gusteau</h1>

<p align="center">
  <em>Healthy recipes, a weekly plan and the shopping list, all from one small kitchen.</em><br>
  <sub>self-hosted · local-only · Cooklang recipes · UI in Spanish</sub>
</p>

> *"Anyone can cook."*

The name nods to the chef whose motto says a great cook can come from anywhere. In that spirit, Gusteau stays small: plain-text recipes you can read and edit, a week that fills itself in, and a shopping list grouped by aisle. No accounts, no cloud, no ads. Just you and the stove.

A minimalist bank of healthy recipes plus a weekly planner that tells you what to buy.

- Recipes are plain [Cooklang](https://cooklang.org) files (`recipes/*.cook`), written for 1 serving.
- A weekly plan (breakfast, lunch, dinner) is generated from the bank or filled in by hand.
- The shopping list adds up every ingredient in the plan, scaled to the number of people (default 2), grouped by aisle in the order of `aisles.yml`.

## Run

```bash
(cd frontend && npm ci && npm run build)   # builds the UI into gusteau/static
uv sync
uv run gusteau                             # http://localhost:8000, API docs at /api/docs
uv run pytest
```

Frontend dev with hot reload: `uv run gusteau` in one shell, `cd frontend && npm run dev` in another (Vite proxies `/api` to :8000).

## Develop

```
gusteau/
  cooklang.py   parser            planner.py   weekly plan generator
  shopping.py   list + units      mercadona.py  product search, packs, prices (unofficial)
  store.py      data dir (atomic writes, recipe cache, seed sync)
  api/          FastAPI routers (recipes, plans, shopping, settings) + schemas.py (the API contract)
frontend/src/
  pages/  components/  lib/api.ts (client) + lib/api.gen.ts (generated types)
tests/          one file per module, shared fakes in conftest.py
```

- Checks: `uv run ruff format --check . && uv run ruff check . && uv run pytest`, and `npm run lint && npm run build` in `frontend/`. CI (`.github/workflows/ci.yml`) runs them all and builds the Docker image.
- After changing anything in `gusteau/api/schemas.py`, run `npm run gen:api` in `frontend/`: it regenerates `openapi.json` and the TypeScript types. Commit both generated files; CI fails if they are stale.

Environment variables:

| Variable         | Default                | Purpose                                 |
| ---------------- | ---------------------- | --------------------------------------- |
| `GUSTEAU_DATA`   | `./data`               | recipes, plans and settings (on disk)   |
| `GUSTEAU_PORT`   | `8000`                 | HTTP port                               |
| `GUSTEAU_STATIC` | `gusteau/static`       | built frontend served at `/`            |

On every start the bundled `recipes/` and `aisles.yml` are synced into `GUSTEAU_DATA`: new recipes are added and untouched ones updated; recipes you edited or deleted are left alone, and new ingredients are appended to a customised `aisles.yml`.

## Recipe format

```
---
title: Pollo con arroz y brócoli
servings: 1
tags: [comida]
time: 30 min
---
Cuece @arroz integral{75%g} 25 minutos.

Haz a la plancha @pechuga de pollo{150%g} con @aceite de oliva virgen extra{10%ml}.
```

- `tags` containing `desayuno`, `comida` or `cena` decide which slots a recipe can fill (no slot tag = any slot).
- Units `g/kg`, `ml/l` and plain counts are merged; anything else is summed per unit. `@sal` without quantity shows as "al gusto".
- Supported Cooklang subset: front matter, ingredients, cookware (`#`), timers (`~`), comments (`--`, `[- -]`).
- Planner tags: `habitual` (your usual dishes, proposed more often: ~5 breakfasts and 4–6 lunches/dinners a week, each main at most twice), `finde` (long recipes, Saturday/Sunday only), `legumbre` / `pescado` / `carne` (weekly balance: 3–4 / 2–3 / 2–4).

## Mercadona prices

The shopping list shows, per ingredient, the Mercadona product, how many packs to buy, its price and a weekly total (`~` = sold by weight, estimated). Click the product line to pick another one or mark the ingredient as not bought there.

- `products.yml` maps ingredients to product ids (warehouse `mad1`, Madrid); your picks are saved to `GUSTEAU_DATA/products.yml` and win. Unmapped ingredients are auto-mapped to the first available search hit.
- Items where the week uses under 15 % of a pack (spices, oil, vinegar) are flagged "¿en casa?" and left out of the total.
- **Unofficial.** Mercadona has no public API: Gusteau reads the same Algolia search index the shop's website uses, with the public search-only key from its JS bundle. Read-only, cached for 24 h in `GUSTEAU_DATA/.cache/`. If it changes or blocks access, the list keeps working without prices. Turn it off with `PUT /api/settings {"prices": false}`.

## API

| Method | Path                                  |                                   |
| ------ | ------------------------------------- | --------------------------------- |
| GET    | `/api/recipes`                        | list                              |
| GET/PUT/DELETE | `/api/recipes/{slug}`         | detail (with source) / edit / delete |
| POST   | `/api/recipes`                        | create from Cooklang source       |
| GET/PUT | `/api/plans/{YYYY-Www}`              | weekly plan                       |
| POST   | `/api/plans/{week}/generate`          | fill empty slots (`keep: false` to redo all) |
| GET    | `/api/plans/{week}/shopping[.md]`     | shopping list (`?people=N`)       |
| GET/PUT | `/api/settings`                      | `people`, `prices`                |
| GET    | `/api/products/search?q=`             | Mercadona product search          |
| PUT    | `/api/products/{ingredient}`          | pick product (`{"id": null}` = not at Mercadona) |

## Branding

The logo (`docs/logo.svg`, also `frontend/public/favicon.svg`) is an original drawing: a chef's toque with a small tail peeking out. The UI uses a bistro palette (burgundy, brass and cream) on top of the zinc shadcn base, and Fraunces (bundled with `@fontsource-variable/fraunces`, so it works offline) for headings.

---

<sub>Gusteau is an unofficial, fan-named personal project. It is not affiliated with, endorsed by or connected to Disney or Pixar. No official artwork is used; the only references are short quotes and the name.</sub>
