from __future__ import annotations

import os
from pathlib import Path

from alembic import context

from gusteau.db import Base, make_engine

config = context.config
# called from gusteau.db.migrate() with the app's engine, or from the alembic CLI (alembic.ini)
engine = config.attributes.get("engine") or make_engine(Path(os.environ.get("GUSTEAU_DATA", "data")) / "gusteau.db")

with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=True,  # SQLite can't ALTER most things: migrations rebuild the table instead
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
    connection.commit()
