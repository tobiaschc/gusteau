"""Print the OpenAPI schema: `python -m gusteau.api.openapi > frontend/openapi.json`.

The frontend generates its API types from that file (`npm run gen:api`); CI fails if
either is stale, so backend and frontend cannot drift apart silently.
"""

import json
import sys
import tempfile

from ..store import Store
from . import create_app


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        schema = create_app(Store(tmp), static_dir=None).openapi()
    json.dump(schema, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
