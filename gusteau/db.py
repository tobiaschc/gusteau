"""SQLite database: SQLAlchemy models, engine and schema migrations (Alembic).

Plans and settings live here; recipes stay as .cook files (hand-editable, git-friendly).
The schema is created and upgraded on startup by running the Alembic migrations in
`gusteau/migrations`. After changing a model, add a migration:

    GUSTEAU_DATA=./data uv run alembic revision --autogenerate -m "describe the change"
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Engine,
    Float,
    ForeignKey,
    Integer,
    String,
    TypeDecorator,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

MIGRATIONS = Path(__file__).resolve().parent / "migrations"


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class UTCDateTime(TypeDecorator):
    """Aware UTC datetimes. SQLite has no timezone type and hands back naive values, which
    the API would serialise without an offset (and browsers would read as local time)."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: dt.datetime | None, _dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime: use an aware UTC value")
        return value.astimezone(dt.UTC).replace(tzinfo=None)

    def process_result_value(self, value: dt.datetime | None, _dialect):
        return value.replace(tzinfo=dt.UTC) if value is not None else None


class Base(DeclarativeBase):
    pass


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[object] = mapped_column(JSON)


class Plan(Base):
    __tablename__ = "plans"

    week: Mapped[str] = mapped_column(String(8), primary_key=True)  # ISO week, 2026-W40
    updated_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
    meals: Mapped[list[Meal]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class Meal(Base):
    """One filled slot of a weekly plan. Empty slots have no row."""

    __tablename__ = "meals"
    __table_args__ = (UniqueConstraint("week", "day", "slot"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    week: Mapped[str] = mapped_column(ForeignKey("plans.week", ondelete="CASCADE"), index=True)
    day: Mapped[str] = mapped_column(String(10))
    slot: Mapped[str] = mapped_column(String(20))
    recipe_slug: Mapped[str] = mapped_column(String(120), index=True)
    # title at planning time: history stays readable if the recipe is renamed or deleted
    recipe_title: Mapped[str] = mapped_column(String(200))
    # what actually happened; None = cooked as planned (the default once the day has passed)
    status: Mapped[str | None] = mapped_column(String(10), default=None)  # "skipped" | "swapped"
    swap_slug: Mapped[str | None] = mapped_column(String(120), default=None)  # "swapped": the recipe eaten instead,
    swap_title: Mapped[str | None] = mapped_column(String(200), default=None)  # or just a free-text title
    plan: Mapped[Plan] = relationship(back_populates="meals")


class Purchase(Base):
    """A shopping trip: the week's list frozen with the Mercadona prices of that moment."""

    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    week: Mapped[str] = mapped_column(ForeignKey("plans.week", ondelete="CASCADE"), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)
    people: Mapped[int] = mapped_column(Integer)
    estimated_total: Mapped[float | None] = mapped_column(Float)  # Mercadona estimate (None: no prices then)
    actual_total: Mapped[float | None] = mapped_column(Float, default=None)  # from the receipt, if entered
    items: Mapped[list] = mapped_column(JSON)  # [{name, amounts, product_id, product, packs, cost, pantry}]


class ShoppingMark(Base):
    """Shared state of one shopping-list line for a week. A row only exists while some
    field differs from its default (not in the cart, pantry question unanswered)."""

    __tablename__ = "shopping_marks"

    week: Mapped[str] = mapped_column(ForeignKey("plans.week", ondelete="CASCADE"), primary_key=True)
    ingredient: Mapped[str] = mapped_column(String(120), primary_key=True)
    in_cart: Mapped[bool] = mapped_column(Boolean, default=False)
    # for "¿en casa?" items: True = we have it (hide), False = we're out (buy it), None = unanswered
    at_home: Mapped[bool | None] = mapped_column(Boolean, default=None)


def make_engine(path: Path) -> Engine:
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _record) -> None:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")  # readers don't block the writer
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=5000")  # concurrent writers wait instead of failing
        cur.close()

    return engine


def alembic_config(engine: Engine | None = None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    if engine is not None:
        cfg.attributes["engine"] = engine
    return cfg


def migrate(engine: Engine) -> None:
    """Create or upgrade the schema to the latest migration."""
    command.upgrade(alembic_config(engine), "head")
