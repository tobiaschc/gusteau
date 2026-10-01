"""Fill a weekly plan with recipes from the bank."""

from __future__ import annotations

import random
from collections import Counter
from itertools import pairwise

from .cooklang import Recipe

ATTEMPTS = 400
MAIN_SLOTS = ("comida", "cena")
# Weekly target for lunches + dinners, per protein tag (min, max). Roughly a Mediterranean week.
BALANCE = {"legumbre": (3, 4), "pescado": (2, 3), "carne": (2, 3)}


def penalty(days: dict[str, dict[str, str | None]], tags: dict[str, list[str]] | None = None) -> int:
    """Lower is better. In order of weight: same recipe twice in a day, same slot on
    consecutive days, protein balance off target, same protein twice in a day, repeats."""
    tags = tags or {}
    slots = list(next(iter(days.values()), {}))
    score = 0
    for day in days.values():
        picked = [s for s in day.values() if s]
        score += 100 * (len(picked) - len(set(picked)))
        mains = [t for slot in MAIN_SLOTS if day.get(slot) for t in tags.get(day[slot], []) if t in BALANCE]
        score += 3 * (len(mains) - len(set(mains)))
    for slot in slots:
        seq = [day[slot] for day in days.values()]
        score += 10 * sum(1 for a, b in pairwise(seq) if a and a == b)
    week = Counter(s for day in days.values() for s in day.values() if s)
    score += 2 * sum(c - 1 for c in week.values())
    counts = Counter(
        t for day in days.values() for slot in MAIN_SLOTS if day.get(slot) for t in tags.get(day[slot], [])
    )
    for tag, (lo, hi) in BALANCE.items():
        score += 5 * (max(0, lo - counts[tag]) + max(0, counts[tag] - hi))
    return score


WEEKEND = ("sabado", "domingo")


def _fill_once(start, slots, pools, known, rng, weekend_only=frozenset()):
    out = {d: dict(v) for d, v in start.items()}
    order = list(out)
    for slot in rng.sample(slots, len(slots)):
        pool = pools[slot]
        if not pool:
            continue
        used = Counter(out[d][slot] for d in order if out[d][slot] in known)
        for i, d in enumerate(order):
            if out[d][slot] in known:
                continue
            avoid = set(out[d].values())
            if i:
                avoid.add(out[order[i - 1]][slot])
            if i + 1 < len(order):
                avoid.add(out[order[i + 1]][slot])
            allowed = [s for s in pool if d in WEEKEND or s not in weekend_only] or pool
            choices = [s for s in allowed if s not in avoid] or allowed
            least = min(used[s] for s in choices)
            pick = rng.choice([s for s in choices if used[s] == least])
            out[d][slot] = pick
            used[pick] += 1
    return out


def generate(plan: dict, recipes: list[Recipe], keep: bool = True, seed: int | None = None) -> dict:
    """Fill the empty slots of `plan`.

    A recipe can go in a slot if it has that slot as a tag (recipes without any slot
    tag fit anywhere). Avoids the same recipe twice in one day or in the same slot on
    consecutive days, spreads repeats, and balances legumes / fish / meat across the
    week's lunches and dinners (see BALANCE). `keep=False` refills every slot.
    Greedy fill with random restarts; the plan with the lowest `penalty` wins.
    """
    rng = random.Random(seed)
    slots = list(next(iter(plan["days"].values()), {}))
    known = {r.slug for r in recipes}
    tags = {r.slug: r.tags for r in recipes}
    weekend_only = frozenset(r.slug for r in recipes if "finde" in r.tags)  # long recipes: Sat/Sun only
    pools = {slot: [r.slug for r in recipes if slot in r.tags or not (set(slots) & set(r.tags))] for slot in slots}
    start = {d: {s: (v if keep and v in known else None) for s, v in day.items()} for d, day in plan["days"].items()}

    best, best_score = start, None
    for _ in range(ATTEMPTS):
        candidate = _fill_once(start, slots, pools, known, rng, weekend_only)
        score = penalty(candidate, tags)
        if best_score is None or score < best_score:
            best, best_score = candidate, score
        if score == 0:
            break
    return {**plan, "days": best}
