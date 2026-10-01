from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Query

from .. import stats
from .deps import StoreDep
from .schemas import Stats

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=Stats)
def get_stats(
    store: StoreDep,
    weeks: Annotated[int, Query(ge=0, le=520, description="last N weeks, this one included; 0 = all")] = 26,
    today: Annotated[dt.date | None, Query(include_in_schema=False)] = None,  # tests
):
    today = today or dt.datetime.now().astimezone().date()
    since = stats.iso_week(today - dt.timedelta(weeks=weeks - 1)) if weeks else None
    with store.session() as s:
        eaten = stats.eaten(s, today, since)
        skipped = stats.skipped(s, today, since)
        spending = stats.spending(s, since)
    seen = {d["slug"] for d in eaten if not d["breakfast"]}
    never = [
        {"slug": r.slug, "title": r.title}
        for r in store.list_recipes()
        if r.slug not in seen and ({"comida", "cena"} & set(r.tags) or "desayuno" not in r.tags)
    ]
    return Stats(
        since=since,
        meals_eaten=sum(d["count"] for d in eaten),
        meals_skipped=skipped,
        dishes=[d for d in eaten if not d["breakfast"]],
        breakfasts=[d for d in eaten if d["breakfast"]],
        never_eaten=never,
        spending=spending,
    )
