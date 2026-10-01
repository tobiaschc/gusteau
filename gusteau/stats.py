"""Statistics over the history in the database: what was actually eaten, and what was spent.

"Eaten" = meals of past days (today included) that weren't marked skipped; swapped meals
count as what was eaten instead. Aggregation runs in SQL; dates are rebuilt from (week, day).
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict

from sqlalchemy import String, and_, case, cast, func, or_, select
from sqlalchemy.orm import Session

from . import db
from .store import DAYS


def iso_week(day: dt.date) -> str:
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


def week_day(week: str, index: int) -> dt.date:
    y, w = week.split("-W")
    return dt.date.fromisocalendar(int(y), int(w), index + 1)


def eaten(session: Session, today: dt.date, since: str | None) -> list[dict]:
    """Dishes actually eaten, most frequent first: [{slug, title, breakfast, count, last}]."""
    m = db.Meal
    day_idx = case({d: i for i, d in enumerate(DAYS)}, value=m.day, else_=0)
    current = iso_week(today)
    swapped = m.status == "swapped"
    # recipe or free text; free-text keys are normalised so "Pizza fuera" == "pizza fuera"
    key = case((swapped, func.coalesce(m.swap_slug, "txt:" + func.lower(func.trim(m.swap_title)))), else_=m.recipe_slug)
    title = case((swapped, m.swap_title), else_=m.recipe_title)
    last = func.max(m.week + "-" + cast(day_idx, String))  # "2026-W40-3": sorts chronologically
    query = (
        select(key, func.max(title), m.slot == "desayuno", func.count(), last)
        .where(
            or_(m.status.is_(None), swapped),
            or_(m.week < current, and_(m.week == current, day_idx <= today.weekday())),
        )
        .group_by(key, m.slot == "desayuno")
        .order_by(func.count().desc(), last.desc())
    )
    if since:
        query = query.where(m.week >= since)
    return [
        {
            "slug": None if k.startswith("txt:") else k,
            "title": t,
            "breakfast": bool(b),
            "count": n,
            "last": week_day(lw[:8], int(lw[9:])),
        }
        for k, t, b, n, lw in session.execute(query)
    ]


def skipped(session: Session, today: dt.date, since: str | None) -> int:
    m = db.Meal
    query = select(func.count()).where(m.status == "skipped", m.week <= iso_week(today))
    if since:
        query = query.where(m.week >= since)
    return session.scalar(query) or 0


def spending(session: Session, since: str | None) -> dict:
    """Per week and per month (month of the week's Thursday, as ISO weeks do). A purchase counts
    its receipt total if entered, otherwise the Mercadona estimate; `exact` = all receipts."""
    p = db.Purchase
    amount = func.coalesce(p.actual_total, p.estimated_total)
    query = (
        select(p.week, func.sum(amount), func.min(case((p.actual_total.is_(None), 0), else_=1)), func.count())
        .where(amount.is_not(None))
        .group_by(p.week)
        .order_by(p.week)
    )
    if since:
        query = query.where(p.week >= since)
    weeks = [
        {"week": w, "total": round(t, 2), "exact": bool(e), "purchases": n} for w, t, e, n in session.execute(query)
    ]
    months: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "exact": True})
    for w in weeks:
        month = week_day(w["week"], 3).strftime("%Y-%m")
        months[month]["total"] += w["total"]
        months[month]["exact"] &= w["exact"]
    total = round(sum(w["total"] for w in weeks), 2) if weeks else None
    return {
        "weeks": weeks,
        "months": [{"month": k, "total": round(v["total"], 2), "exact": v["exact"]} for k, v in sorted(months.items())],
        "total": total,
        "average_week": round(total / len(weeks), 2) if weeks else None,
    }
