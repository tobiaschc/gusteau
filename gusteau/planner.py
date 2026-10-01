"""Fill a weekly plan with recipes from the bank."""

from __future__ import annotations

import random
from collections import Counter
from itertools import pairwise

from .cooklang import Recipe

ATTEMPTS = 200


def penalty(days: dict[str, dict[str, str | None]]) -> int:
    """Lower is better: same recipe twice in a day > same slot on consecutive days > repeats."""
    slots = list(next(iter(days.values()), {}))
    score = 0
    for day in days.values():
        picked = [s for s in day.values() if s]
        score += 100 * (len(picked) - len(set(picked)))
    for slot in slots:
        seq = [day[slot] for day in days.values()]
        score += 10 * sum(1 for a, b in pairwise(seq) if a and a == b)
        score += sum(c - 1 for c in Counter(s for s in seq if s).values())
    return score


def _fill_once(start, slots, pools, known, rng):
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
            choices = [s for s in pool if s not in avoid] or pool
            least = min(used[s] for s in choices)
            pick = rng.choice([s for s in choices if used[s] == least])
            out[d][slot] = pick
            used[pick] += 1
    return out


def generate(plan: dict, recipes: list[Recipe], keep: bool = True, seed: int | None = None) -> dict:
    """Fill the empty slots of `plan`.

    A recipe can go in a slot if it has that slot as a tag (recipes without any slot
    tag fit anywhere). Avoids the same recipe twice in one day or in the same slot on
    consecutive days, and spreads repeats evenly. `keep=False` refills every slot.
    Greedy fill with random restarts; the plan with the lowest `penalty` wins.
    """
    rng = random.Random(seed)
    slots = list(next(iter(plan["days"].values()), {}))
    known = {r.slug for r in recipes}
    pools = {slot: [r.slug for r in recipes if slot in r.tags or not (set(slots) & set(r.tags))] for slot in slots}
    start = {d: {s: (v if keep and v in known else None) for s, v in day.items()} for d, day in plan["days"].items()}

    best, best_score = start, None
    for _ in range(ATTEMPTS):
        candidate = _fill_once(start, slots, pools, known, rng)
        score = penalty(candidate)
        if best_score is None or score < best_score:
            best, best_score = candidate, score
        if score == 0:
            break
    return {**plan, "days": best}
