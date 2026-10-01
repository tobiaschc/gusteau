"""Small Cooklang parser covering the subset Gusteau uses.

Supported (https://cooklang.org/docs/spec/):
- YAML front matter between leading `---` lines (title, servings, tags, time, ...)
- ingredients: @name{qty%unit}, @name{qty}, @name{}, @word
- cookware:    #name{}, #word
- timers:      ~{qty%unit}, ~name{qty%unit}
- comments:    -- to end of line, [- block -]
- steps: one per paragraph (blank line separated); single newlines are joined.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction

import yaml

FRONT_MATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.DOTALL)
BLOCK_COMMENT = re.compile(r"\[-.*?-\]", re.DOTALL)
LINE_COMMENT = re.compile(r"--.*$", re.MULTILINE)
TOKEN = re.compile(
    r"(?P<kind>[@#~])"
    r"(?:(?P<multi>[^@#~{}\n]*?)\{(?P<amount>[^}]*)\}|(?P<word>[^\s@#~{}.,;:!?()]+))"
)


class CooklangError(ValueError):
    pass


@dataclass
class Ingredient:
    name: str
    quantity: float | None
    unit: str


@dataclass
class Recipe:
    slug: str
    title: str
    servings: int
    tags: list[str]
    time: str | None
    ingredients: list[Ingredient]
    steps: list[list[dict]]  # each step is a list of segments for rendering
    meta: dict = field(default_factory=dict)


def parse_quantity(text: str) -> float | None:
    text = text.strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(sum(Fraction(part) for part in text.split()))  # "1 1/2", "1/2", "2.5"
    except (ValueError, ZeroDivisionError) as e:
        raise CooklangError(f"invalid quantity {text!r}") from e


def _amount(raw: str | None) -> tuple[float | None, str]:
    qty, _, unit = (raw or "").partition("%")
    return parse_quantity(qty), unit.strip()


def parse(text: str, slug: str = "") -> Recipe:
    meta: dict = {}
    m = FRONT_MATTER.match(text)
    if m:
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as e:
            raise CooklangError(f"invalid front matter: {e}") from e
        if not isinstance(meta, dict):
            raise CooklangError("front matter must be a mapping")
        text = text[m.end() :]

    body = LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", text))
    paragraphs = [" ".join(line.strip() for line in p.splitlines() if line.strip()) for p in re.split(r"\n\s*\n", body)]

    ingredients: list[Ingredient] = []
    steps: list[list[dict]] = []
    for para in filter(None, paragraphs):
        segments: list[dict] = []
        pos = 0
        for t in TOKEN.finditer(para):
            if t.start() > pos:
                segments.append({"type": "text", "value": para[pos : t.start()]})
            pos = t.end()
            kind = t.group("kind")
            name = (t.group("multi") if t.group("amount") is not None else t.group("word")) or ""
            name = name.strip()
            qty, unit = _amount(t.group("amount"))
            if kind == "@":
                if not name:
                    raise CooklangError(f"ingredient without name near {para[t.start() : t.end() + 10]!r}")
                ingredients.append(Ingredient(name.lower(), qty, unit.lower()))
                segments.append({"type": "ingredient", "name": name, "quantity": qty, "unit": unit})
            elif kind == "#":
                segments.append({"type": "cookware", "name": name})
            else:
                segments.append({"type": "timer", "name": name, "quantity": qty, "unit": unit})
        if pos < len(para):
            segments.append({"type": "text", "value": para[pos:]})
        steps.append(segments)

    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    try:
        servings = int(meta.get("servings", 1))
    except (TypeError, ValueError) as e:
        raise CooklangError(f"invalid servings {meta.get('servings')!r}") from e
    if servings < 1:
        raise CooklangError("servings must be >= 1")

    return Recipe(
        slug=slug,
        title=str(meta.get("title") or slug.replace("-", " ").capitalize()),
        servings=servings,
        tags=[str(t).strip().lower() for t in tags if str(t).strip()],
        time=str(meta["time"]) if meta.get("time") else None,
        ingredients=ingredients,
        steps=steps,
        meta={k: v for k, v in meta.items() if k not in {"title", "servings", "tags", "time"}},
    )
