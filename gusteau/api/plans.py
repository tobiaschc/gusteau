from __future__ import annotations

import datetime as dt

from fastapi import APIRouter

from .. import planner
from ..store import Store
from .deps import StoreDep, Week, recipe_or_404
from .schemas import GenerateIn, Plan, PlanIn

router = APIRouter(prefix="/plans", tags=["plans"])


def current_week(today: dt.date | None = None) -> str:
    y, w, _ = (today or dt.datetime.now().astimezone().date()).isocalendar()
    return f"{y}-W{w:02d}"


def plan_view(store: Store, plan: dict) -> Plan:
    titles = {r.slug: r.title for r in store.list_recipes()}
    planned = plan.get("titles", {})  # title when planned: shown if the recipe was renamed or deleted
    used = {s for day in plan["days"].values() for s in day.values() if s}
    return Plan(week=plan["week"], days=plan["days"], titles={s: titles.get(s) or planned.get(s) for s in used})


@router.get("/current", response_model=Plan)
def get_current_plan(store: StoreDep):
    return plan_view(store, store.get_plan(current_week()))


@router.get("/{week}", response_model=Plan)
def get_plan(week: Week, store: StoreDep):
    return plan_view(store, store.get_plan(week))


@router.put("/{week}", response_model=Plan)
def put_plan(week: Week, body: PlanIn, store: StoreDep):
    for slots in body.days.values():
        for slug in filter(None, slots.values()):
            recipe_or_404(store, slug)
    return plan_view(store, store.save_plan({"week": week, "days": body.days}))


@router.post("/{week}/generate", response_model=Plan)
def generate_plan(week: Week, body: GenerateIn, store: StoreDep):
    plan = planner.generate(store.get_plan(week), store.list_recipes(), keep=body.keep, seed=body.seed)
    return plan_view(store, store.save_plan(plan))
