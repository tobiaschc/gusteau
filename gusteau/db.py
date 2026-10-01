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
from sqlalchemy import JSON, DateTime, Engine, ForeignKey, String, UniqueConstraint, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

MIGRATIONS = Path(__file__).resolve().parent / "migrations"


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class Base(DeclarativeBase):
    pass


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[object] = mapped_column(JSON)


class Plan(Base):
    __tablename__ = "plans"

    week: Mapped[str] = mapped_column(String(8), primary_key=True)  # ISO week, 2026-W40
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
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
    plan: Mapped[Plan] = relationship(back_populates="meals")


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
