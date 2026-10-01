"""Fill a weekly plan with recipes from the bank."""

from __future__ import annotations

import random
from collections import Counter
from itertools import pairwise

from .cooklang import Recipe

ATTEMPTS = 400
MAIN_SLOTS = ("comida", "cena")
WEEKEND = ("sabado", "domingo")
# Weekly target for lunches + dinners, per protein tag (min, max). Roughly a Mediterranean week.
BALANCE = {"legumbre": (3, 4), "pescado": (2, 3), "carne": (2, 4)}
# Recipes tagged `habitual` are the household's usual dishes and show up more often.
# Per slot group: (min, max) habitual meals per week, and the chance the greedy fill picks one.
HABITUAL = "habitual"
HABITUAL_TARGET = {"desayuno": (5, 6), "main": (4, 6)}
HABITUAL_PICK = {"desayuno": 0.75, "main": 0.4}
HABITUAL_MAX_EACH = 2  # a usual lunch/dinner at most twice a week


def _group(slot: str) -> str:
    return "main" if slot in MAIN_SLOTS else slot


def penalty(days: dict[str, dict[str, str | None]], tags: dict[str, list[str]] | None = None) -> int:
    """Lower is better. In order of weight: same recipe twice in a day, same lunch/dinner
    on consecutive days, protein balance off target, habitual share off target, same
    protein twice in a day, repeats. Breakfasts may repeat on consecutive days."""
    tags = tags or {}

    def habitual(s: str | None) -> bool:
        return bool(s) and HABITUAL in tags.get(s, [])

    slots = list(next(iter(days.values()), {}))
    score = 0
    for day in days.values():
        picked = [s for s in day.values() if s]
        score += 100 * (len(picked) - len(set(picked)))
        mains = [t for slot in MAIN_SLOTS for t in tags.get(day.get(slot) or "", []) if t in BALANCE]
        score += 3 * (len(mains) - len(set(mains)))
    for slot in slots:
        if _group(slot) != "main":
            continue
        seq = [day[slot] for day in days.values()]
        score += 10 * sum(1 for a, b in pairwise(seq) if a and a == b)
    week = Counter(s for day in days.values() for s in day.values() if s)
    score += 2 * sum(c - 1 for s, c in week.items() if not habitual(s))
    main_week = Counter(day[slot] for day in days.values() for slot in MAIN_SLOTS if day.get(slot))
    score += 5 * sum(max(0, c - HABITUAL_MAX_EACH) for s, c in main_week.items() if habitual(s))
    counts = Counter(t for s, c in main_week.items() for t in tags.get(s, []) for _ in range(c))
    for tag, (lo, hi) in BALANCE.items():
        score += 5 * (max(0, lo - counts[tag]) + max(0, counts[tag] - hi))
    for group, (lo, hi) in HABITUAL_TARGET.items():
        group_slots = {s for s in slots if _group(s) == group}
        # only enforce the share when the bank has usual recipes for this group
        if not any(habitual(r) and group_slots & set(t) for r, t in tags.items()):
            continue
        n = sum(habitual(day[s]) for day in days.values() for s in group_slots)
        score += 4 * (max(0, lo - n) + max(0, n - hi))
    return score


def _fill_once(start, slots, pools, known, rng, weekend_only=frozenset(), habitual=frozenset()):
    out = {d: dict(v) for d, v in start.items()}
    order = list(out)
    for slot in rng.sample(slots, len(slots)):
        pool = pools[slot]
        if not pool:
            continue
        group = _group(slot)
        used = Counter(out[d][slot] for d in order if out[d][slot] in known)
        for i, d in enumerate(order):
            if out[d][slot] in known:
                continue
            avoid = set(out[d].values())
            if group == "main":
                if i:
                    avoid.add(out[order[i - 1]][slot])
                if i + 1 < len(order):
                    avoid.add(out[order[i + 1]][slot])
            allowed = [s for s in pool if d in WEEKEND or s not in weekend_only] or pool
            choices = [s for s in allowed if s not in avoid] or allowed
            usual = [s for s in choices if s in habitual]
            if usual and rng.random() < HABITUAL_PICK.get(group, 0):
                pick = rng.choice(usual)
            else:
                rest = [s for s in choices if s not in habitual] or choices
                least = min(used[s] for s in rest)
                pick = rng.choice([s for s in rest if used[s] == least])
            out[d][slot] = pick
            used[pick] += 1
    return out


def generate(plan: dict, recipes: list[Recipe], keep: bool = True, seed: int | None = None) -> dict:
    """Fill the empty slots of `plan`.

    A recipe can go in a slot if it has that slot as a tag (recipes without any slot
    tag fit anywhere). Avoids the same recipe twice in one day or the same lunch/dinner
    on consecutive days, spreads repeats, balances legumes / fish / meat across the
    week's lunches and dinners (BALANCE), favours `habitual` recipes (HABITUAL_TARGET)
    and keeps `finde` recipes for the weekend. `keep=False` refills every slot.
    Greedy fill with random restarts; the plan with the lowest `penalty` wins and is
    then polished by a single-slot hill-climb.
    """
    rng = random.Random(seed)
    slots = list(next(iter(plan["days"].values()), {}))
    known = {r.slug for r in recipes}
    tags = {r.slug: r.tags for r in recipes}
    weekend_only = frozenset(r.slug for r in recipes if "finde" in r.tags)  # long recipes: Sat/Sun only
    habitual = frozenset(r.slug for r in recipes if HABITUAL in r.tags)
    pools = {slot: [r.slug for r in recipes if slot in r.tags or not (set(slots) & set(r.tags))] for slot in slots}
    start = {d: {s: (v if keep and v in known else None) for s, v in day.items()} for d, day in plan["days"].items()}

    best, best_score = start, None
    for _ in range(ATTEMPTS):
        candidate = _fill_once(start, slots, pools, known, rng, weekend_only, habitual)
        score = penalty(candidate, tags)
        if best_score is None or score < best_score:
            best, best_score = candidate, score
        if score == 0:
            break
    if best_score:
        best = _improve(best, start, pools, known, tags, weekend_only, rng)
    return {**plan, "days": best}


def _improve(days, start, pools, known, tags, weekend_only, rng, max_rounds=5):
    """Hill-climb: re-pick single free slots while that lowers the penalty. The greedy
    restarts find a good shape; this fixes the last few conflicts they leave behind."""
    days = {d: dict(v) for d, v in days.items()}
    score = penalty(days, tags)
    free = [(d, s) for d, day in start.items() for s in day if day[s] not in known]
    for _ in range(max_rounds):
        improved = False
        for d, s in rng.sample(free, len(free)):
            current = days[d][s]
            for slug in pools[s]:
                if slug == current or (d not in WEEKEND and slug in weekend_only):
                    continue
                days[d][s] = slug
                new = penalty(days, tags)
                if new < score:
                    score, current, improved = new, slug, True
                else:
                    days[d][s] = current
            if score == 0:
                return days
        if not improved:
            break
    return days
