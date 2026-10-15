"""Storage: recipes are .cook files, plans and settings live in SQLite (gusteau/db.py).

Layout under GUSTEAU_DATA (default ./data):
    recipes/<slug>.cook
    gusteau.db      plans, meal outcomes, purchases, settings (SQLite; schema migrated on startup)
    aisles.yml      ingredient -> supermarket aisle (optional)
    products.yml    your ingredient -> Mercadona product picks (override the bundled ones)
    .cache/         Mercadona responses
    .seeded.json    hashes of the bundled files last copied in (to sync app updates)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
import unicodedata
from pathlib import Path

import yaml
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session, sessionmaker

from . import db
from .cooklang import Recipe, parse

DAYS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
SLOTS = ["desayuno", "comida", "cena"]
DEFAULT_SETTINGS = {"people": 2, "slots": SLOTS, "prices": True, "warehouse": "mad1", "favorite_ingredients": []}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
WEEK = re.compile(r"^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$")
SEED = Path(__file__).resolve().parent.parent / "recipes"
SEED_AISLES = Path(__file__).resolve().parent.parent / "aisles.yml"
SEED_PRODUCTS = Path(__file__).resolve().parent.parent / "products.yml"


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "receta"


def atomic_write(path: Path, text: str) -> None:
    """Write `text` to `path` so readers see the old or the new file, never half of one.

    Temp file in the same directory + fsync + os.replace (atomic on POSIX). Protects
    against a crash or container stop mid-write; concurrent writers still need a lock.
    """
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _merge_aisles(local: Path, bundled: Path) -> None:
    """Add bundled ingredients missing from a user-edited aisles.yml, keeping their choices."""
    mine = yaml.safe_load(local.read_text(encoding="utf-8")) or {}
    known = {str(i).lower() for items in mine.values() for i in items or []}
    for aisle, items in (yaml.safe_load(bundled.read_text(encoding="utf-8")) or {}).items():
        missing = [i for i in items or [] if str(i).lower() not in known]
        if missing:
            mine.setdefault(aisle, [])
            mine[aisle] = list(mine[aisle] or []) + missing
    atomic_write(local, yaml.safe_dump(mine, allow_unicode=True, sort_keys=False, width=120))


class Store:
    """All reads and writes of the data dir.

    Thread-safe within one process (FastAPI runs sync endpoints in a thread pool):
    read-modify-write operations hold `_lock`, and every write is atomic. Parsed
    recipes are cached and re-parsed only when their file changes (mtime/size), so
    listing the bank costs one directory scan. Returned Recipe objects are shared:
    treat them as read-only.
    """

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root or os.environ.get("GUSTEAU_DATA", "data"))
        self.recipes_dir = self.root / "recipes"
        self.recipes_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._recipes: dict[str, tuple[tuple[int, int], Recipe]] = {}
        self.engine = db.make_engine(self.root / "gusteau.db")
        db.migrate(self.engine)
        self.session: sessionmaker[Session] = sessionmaker(self.engine, expire_on_commit=False)
        self.sync_seed()
        self._import_json()

    def sync_seed(self) -> None:
        """Bring bundled recipes and aisles into the data dir without clobbering user edits.

        - new bundled recipe -> copied in
        - bundled recipe changed, local copy untouched since last sync -> updated
        - local copy edited, or deleted by the user -> left alone
        - recipe removed from the bundle -> removed here too, unless the user edited it
        - aisles.yml: replaced if untouched, otherwise new ingredients are appended to their aisle
        """
        state_path = self.root / ".seeded.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        recipes = state.setdefault("recipes", {})
        first_run = not state_path.exists() and not any(self.recipes_dir.glob("*.cook"))
        for src in sorted(SEED.glob("*.cook")) if SEED.is_dir() else []:
            bundled = _digest(src.read_bytes())
            dst = self.recipes_dir / src.name
            seeded = recipes.get(src.stem)
            if seeded is None:
                if not dst.exists() or first_run:
                    atomic_write(dst, src.read_text(encoding="utf-8"))
                    recipes[src.stem] = bundled
                elif _digest(dst.read_bytes()) == bundled:
                    recipes[src.stem] = bundled  # already identical (install from before tracking)
                # else: same slug created by the user -> theirs
            elif seeded != bundled and dst.exists() and _digest(dst.read_bytes()) == seeded:
                atomic_write(dst, src.read_text(encoding="utf-8"))
                recipes[src.stem] = bundled
        bundle = {p.stem for p in SEED.glob("*.cook")} if SEED.is_dir() else set()
        for slug in [s for s in recipes if bundle and s not in bundle]:  # retired from the bundle
            dst = self.recipes_dir / f"{slug}.cook"
            if dst.exists() and _digest(dst.read_bytes()) == recipes[slug]:
                dst.unlink()  # untouched copy -> goes too; an edited one is now the user's own
            del recipes[slug]

        aisles = self.root / "aisles.yml"
        if SEED_AISLES.exists():
            bundled = _digest(SEED_AISLES.read_bytes())
            if not aisles.exists() or _digest(aisles.read_bytes()) in (state.get("aisles"), bundled):
                atomic_write(aisles, SEED_AISLES.read_text(encoding="utf-8"))
                state["aisles"] = bundled
            elif state.get("aisles_bundle") != bundled:
                _merge_aisles(aisles, SEED_AISLES)
            state["aisles_bundle"] = bundled
        atomic_write(state_path, json.dumps(state, indent=2, sort_keys=True))

    # ---- recipes ----

    def _recipe_path(self, slug: str) -> Path:
        if not SLUG.match(slug):
            raise KeyError(slug)
        return self.recipes_dir / f"{slug}.cook"

    def _cached(self, path: Path) -> Recipe:
        st = path.stat()
        key = (st.st_mtime_ns, st.st_size)
        hit = self._recipes.get(path.stem)
        if hit and hit[0] == key:
            return hit[1]
        recipe = parse(path.read_text(encoding="utf-8"), path.stem)
        self._recipes[path.stem] = (key, recipe)
        return recipe

    def list_recipes(self) -> list[Recipe]:
        paths = [p for p in self.recipes_dir.glob("*.cook") if SLUG.match(p.stem)]
        with self._lock:
            recipes = [self._cached(p) for p in paths]
            for gone in self._recipes.keys() - {p.stem for p in paths}:
                del self._recipes[gone]
        return sorted(recipes, key=lambda r: r.title.lower())

    def get_recipe(self, slug: str) -> Recipe:
        path = self._recipe_path(slug)
        try:
            with self._lock:
                return self._cached(path)
        except FileNotFoundError:
            raise KeyError(slug) from None

    def get_source(self, slug: str) -> str:
        path = self._recipe_path(slug)
        if not path.exists():
            raise KeyError(slug)
        return path.read_text(encoding="utf-8")

    def save_recipe(self, source: str, slug: str | None = None) -> Recipe:
        recipe = parse(source, slug or "")  # validate before touching disk
        with self._lock:  # slug allocation + write must not interleave with another create
            if slug is None:
                base = slug = slugify(recipe.title)
                n = 2
                while self._recipe_path(slug).exists():
                    slug, n = f"{base}-{n}", n + 1
            atomic_write(self._recipe_path(slug), source if source.endswith("\n") else source + "\n")
        recipe.slug = slug
        return recipe

    def delete_recipe(self, slug: str) -> None:
        path = self._recipe_path(slug)
        if not path.exists():
            raise KeyError(slug)
        with self._lock:
            path.unlink()
            self._recipes.pop(slug, None)

    # ---- plans ----

    def _empty_days(self) -> dict[str, dict[str, str | None]]:
        return {d: dict.fromkeys(self.settings()["slots"]) for d in DAYS}

    def get_plan(self, week: str) -> dict:
        """{"week", "days": {day: {slot: slug | None}}, "titles": {slug: title when planned},
        "outcomes": {day: {slot: {status, swap_slug, swap_title}}} (only meals not cooked as planned)}"""
        if not WEEK.match(week):
            raise KeyError(week)
        days = self._empty_days()
        titles: dict[str, str] = {}
        outcomes: dict[str, dict[str, dict]] = {}
        with self.session() as s:
            for m in s.scalars(select(db.Meal).where(db.Meal.week == week)):
                days.setdefault(m.day, {})[m.slot] = m.recipe_slug
                titles[m.recipe_slug] = m.recipe_title
                if m.status:
                    outcomes.setdefault(m.day, {})[m.slot] = {
                        "status": m.status,
                        "swap_slug": m.swap_slug,
                        "swap_title": m.swap_title,
                    }
        return {"week": week, "days": days, "titles": titles, "outcomes": outcomes}

    def save_plan(self, plan: dict) -> dict:
        week = plan["week"]
        if not WEEK.match(week):
            raise KeyError(week)
        known = plan.get("titles", {}) | {r.slug: r.title for r in self.list_recipes()}  # current title wins
        with self.session.begin() as s:
            now = db.utcnow()  # upsert: atomic even when two requests save the same new week
            s.execute(
                insert(db.Plan)
                .values(week=week, updated_at=now)
                .on_conflict_do_update(index_elements=[db.Plan.week], set_={"updated_at": now})
            )
            # the upsert above took the write lock, so this read can't go stale before we write
            existing = {(m.day, m.slot): m for m in s.scalars(select(db.Meal).where(db.Meal.week == week))}
            for day, slots in plan["days"].items():
                for slot, slug in slots.items():
                    meal = existing.pop((day, slot), None)
                    if not slug:
                        if meal:
                            s.delete(meal)
                    elif meal is None:
                        s.add(
                            db.Meal(week=week, day=day, slot=slot, recipe_slug=slug, recipe_title=known.get(slug, slug))
                        )
                    elif meal.recipe_slug != slug:  # replanned: the old outcome no longer applies
                        meal.recipe_slug, meal.recipe_title = slug, known.get(slug, slug)
                        meal.status = meal.swap_slug = meal.swap_title = None
            for meal in existing.values():  # slots no longer in the plan
                s.delete(meal)
        return self.get_plan(week)

    def set_outcome(self, week: str, day: str, slot: str, status: str | None, swap_slug=None, swap_title=None) -> dict:
        """Record what happened to a planned meal. status None = cooked as planned."""
        with self.session.begin() as s:
            meal = s.scalar(select(db.Meal).where(db.Meal.week == week, db.Meal.day == day, db.Meal.slot == slot))
            if meal is None:
                raise KeyError(f"{week}/{day}/{slot}")
            meal.status = status
            meal.swap_slug = swap_slug if status == "swapped" else None
            meal.swap_title = swap_title if status == "swapped" else None
        return self.get_plan(week)

    # ---- shopping-list marks (shared between devices) ----

    def shopping_marks(self, week: str) -> dict[str, db.ShoppingMark]:
        with self.session() as s:
            return {m.ingredient: m for m in s.scalars(select(db.ShoppingMark).where(db.ShoppingMark.week == week))}

    def set_shopping_mark(self, week: str, ingredient: str, **fields: bool | None) -> db.ShoppingMark:
        """Update one line's marks (`in_cart`, `at_home`); fields left out keep their value."""
        with self.session.begin() as s:
            if s.get(db.Plan, week) is None:
                raise KeyError(week)
            mark = s.get(db.ShoppingMark, (week, ingredient))
            stored = mark is not None
            if not stored:
                mark = db.ShoppingMark(week=week, ingredient=ingredient, in_cart=False, at_home=None)
            for key, value in fields.items():
                setattr(mark, key, value)
            at_default = not mark.in_cart and mark.at_home is None
            if stored and at_default:  # back to defaults: drop the row
                s.delete(mark)
            elif not stored and not at_default:
                s.add(mark)
        return mark

    def clear_cart(self, week: str) -> None:
        """Untick every line; the "¿en casa?" answers stay."""
        with self.session.begin() as s:
            s.execute(update(db.ShoppingMark).where(db.ShoppingMark.week == week).values(in_cart=False))
            s.execute(delete(db.ShoppingMark).where(db.ShoppingMark.week == week, db.ShoppingMark.at_home.is_(None)))

    # ---- purchases ----

    def add_purchase(self, week: str, people: int, estimated_total: float | None, items: list[dict]) -> db.Purchase:
        with self.session.begin() as s:
            if s.get(db.Plan, week) is None:
                raise KeyError(week)
            purchase = db.Purchase(week=week, people=people, estimated_total=estimated_total, items=items)
            s.add(purchase)
        return purchase

    def purchases(self, week: str | None = None) -> list[db.Purchase]:
        query = select(db.Purchase).order_by(db.Purchase.created_at)
        if week:
            query = query.where(db.Purchase.week == week)
        with self.session() as s:
            return list(s.scalars(query))

    def update_purchase(self, purchase_id: int, actual_total: float | None) -> db.Purchase:
        with self.session.begin() as s:
            purchase = s.get(db.Purchase, purchase_id)
            if purchase is None:
                raise KeyError(purchase_id)
            purchase.actual_total = actual_total
        return purchase

    def delete_purchase(self, purchase_id: int) -> None:
        with self.session.begin() as s:
            purchase = s.get(db.Purchase, purchase_id)
            if purchase is None:
                raise KeyError(purchase_id)
            s.delete(purchase)

    # ---- settings & aisles ----

    def settings(self) -> dict:
        with self.session() as s:
            stored = {row.key: row.value for row in s.scalars(select(db.Setting))}
        return {**DEFAULT_SETTINGS, **stored}

    def save_settings(self, values: dict) -> dict:
        with self.session.begin() as s:
            for key, value in values.items():
                stmt = insert(db.Setting).values(key=key, value=value)
                s.execute(
                    stmt.on_conflict_do_update(index_elements=[db.Setting.key], set_={"value": stmt.excluded.value})
                )
        return self.settings()

    # ---- one-off import from the JSON files used before the database ----

    def _import_json(self) -> None:
        """Move plans/*.json and settings.json into the database, then rename them to *.imported."""
        settings = self.root / "settings.json"
        if settings.exists():
            with self.session.begin() as s:
                for key, value in json.loads(settings.read_text()).items():
                    if s.get(db.Setting, key) is None:
                        s.add(db.Setting(key=key, value=value))
            settings.rename(settings.with_suffix(".json.imported"))
        plans = self.root / "plans"
        if plans.is_dir():
            for path in sorted(plans.glob("*.json")):
                plan = json.loads(path.read_text())
                with self.session() as s:
                    exists = s.get(db.Plan, plan.get("week", "")) is not None
                if WEEK.match(plan.get("week", "")) and not exists:
                    self.save_plan({"week": plan["week"], "days": plan.get("days", {})})
            target = self.root / "plans.imported"
            n = 2
            while target.exists():
                target, n = self.root / f"plans.imported-{n}", n + 1
            plans.rename(target)

    def aisles(self) -> dict[str, str]:
        path = self.root / "aisles.yml"
        if not path.exists():
            return {}
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        # file is grouped by aisle: {Frutería: [tomate, ...]} -> {tomate: Frutería}; dict order = shop order
        return {str(i).lower(): aisle for aisle, items in data.items() for i in items or []}

    # ---- Mercadona products ----

    def products(self) -> dict[str, str | None]:
        """ingredient -> product id (None = not sold). User picks win over the bundled defaults."""
        merged: dict[str, str | None] = {}
        for path in (SEED_PRODUCTS, self.root / "products.yml"):
            if path.exists():
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                merged |= {str(k).lower(): (str(v) if v is not None else None) for k, v in data.items()}
        return merged

    def set_product(self, ingredient: str, product_id: str | None) -> None:
        path = self.root / "products.yml"
        with self._lock:
            data = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {}
            data[ingredient.lower()] = product_id
            atomic_write(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=True))
