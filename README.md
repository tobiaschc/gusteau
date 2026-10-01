# Gusteau

> *"Anyone can cook."*

A minimalist bank of healthy recipes plus a weekly planner that tells you what to buy.

- Recipes are plain [Cooklang](https://cooklang.org) files (`recipes/*.cook`), written for 1 serving.
- A weekly plan (breakfast, lunch, dinner) is generated from the bank or filled in by hand.
- The shopping list adds up every ingredient in the plan, scaled to the number of people (default 2), grouped by aisle.

## Run

```bash
uv sync
uv run gusteau                 # http://localhost:8000, API docs at /api/docs
uv run pytest
```

Environment variables:

| Variable         | Default                | Purpose                                 |
| ---------------- | ---------------------- | --------------------------------------- |
| `GUSTEAU_DATA`   | `./data`               | recipes, plans and settings (on disk)   |
| `GUSTEAU_PORT`   | `8000`                 | HTTP port                               |
| `GUSTEAU_STATIC` | `gusteau/static`       | built frontend served at `/`            |

On first start the bundled `recipes/` and `aisles.yml` are copied into `GUSTEAU_DATA`.

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

## API

| Method | Path                                  |                                   |
| ------ | ------------------------------------- | --------------------------------- |
| GET    | `/api/recipes`                        | list                              |
| GET/PUT/DELETE | `/api/recipes/{slug}`         | detail (with source) / edit / delete |
| POST   | `/api/recipes`                        | create from Cooklang source       |
| GET/PUT | `/api/plans/{YYYY-Www}`              | weekly plan                       |
| POST   | `/api/plans/{week}/generate`          | fill empty slots (`keep: false` to redo all) |
| GET    | `/api/plans/{week}/shopping[.md]`     | shopping list (`?people=N`)       |
| GET/PUT | `/api/settings`                      | `people`                          |
