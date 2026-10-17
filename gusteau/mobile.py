"""In-process API for the mobile app: Pyodide calls `MobileApp.request` instead of going through a web server.

The phone build runs this same backend inside a web worker (no sockets, no threads), so requests are fed straight
into the ASGI app, FastAPI's threadpool hand-off for sync endpoints is replaced by an inline call and outgoing HTTP
(Mercadona prices) goes through the browser.

The worker's file system is in memory: the app persists the data dir itself. `MobileApp` is created from the saved
files and, after each request that may write, reports the files that changed since (`snapshot`), base64-encoded so
JavaScript can store them as-is (IndexedDB, same on the phone as in a desktop browser).
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from starlette.types import Message

from .api import create_app
from .store import Store

READ_ONLY = {"GET", "HEAD", "OPTIONS"}
# derived or disposable: the WAL is checkpointed into gusteau.db before each snapshot, .cache holds Mercadona responses
SKIP_SUFFIXES = ("-wal", "-shm", "-journal")
SKIP_DIRS = {".cache"}


def _browser_http() -> None:
    """No sockets either: route urllib (Mercadona prices) through the browser's XMLHttpRequest."""
    import pyodide_http

    pyodide_http.patch_all()


def _run_sync_inline() -> None:
    """Pyodide has no threads: make anyio's (and so Starlette's/FastAPI's) threadpool run the function inline."""
    import anyio.to_thread

    async def run_sync(func, *args, abandon_on_cancel=False, cancellable=None, limiter=None):
        return func(*args)

    anyio.to_thread.run_sync = run_sync


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class MobileApp:
    def __init__(self, data_dir: Path | str, files: dict[str, str] | None = None):
        """`files`: the saved data dir, relative path -> base64 content, restored before the store opens it."""
        if sys.platform == "emscripten":
            _run_sync_inline()
            _browser_http()
        self.root = Path(data_dir)
        self._saved: dict[str, str] = {}  # relative path -> digest of what the app has stored
        for rel, b64 in (files or {}).items():
            path = self._path(rel)
            path.parent.mkdir(parents=True, exist_ok=True)
            data = base64.b64decode(b64)
            path.write_bytes(data)
            self._saved[rel] = _digest(data)
        self.store = Store(self.root)
        # no static dir: the phone app ships its own frontend, the backend only answers /api
        self.app = create_app(self.store, static_dir=self.root / ".no-static")

    def _path(self, rel: str) -> Path:
        path = (self.root / rel).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError(f"path outside the data dir: {rel}")
        return path

    def _files(self) -> dict[str, Path]:
        files = {}
        for path in self.root.rglob("*"):
            rel = path.relative_to(self.root)
            if path.is_file() and not path.name.endswith(SKIP_SUFFIXES) and not SKIP_DIRS & set(rel.parts):
                files[rel.as_posix()] = path
        return files

    def snapshot(self) -> dict[str, Any]:
        """Files changed or deleted since the last snapshot (or the restore): {changed: {path: base64}, deleted}."""
        with self.store.engine.connect() as conn:  # fold the WAL into gusteau.db so the file alone is consistent
            conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
        current = self._files()
        changed = {}
        for rel, path in current.items():
            data = path.read_bytes()
            digest = _digest(data)
            if self._saved.get(rel) != digest:
                changed[rel] = base64.b64encode(data).decode()
                self._saved[rel] = digest
        deleted = sorted(set(self._saved) - set(current))
        for rel in deleted:
            del self._saved[rel]
        return {"changed": changed, "deleted": deleted}

    async def request(self, method: str, path: str, body: str | None = None) -> dict[str, Any]:
        """Run one HTTP request through the ASGI app: {status, content_type, body (text)}."""
        sent = False
        messages: list[Message] = []

        async def receive() -> Message:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": (body or "").encode(), "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message: Message) -> None:
            messages.append(message)

        route, _, query = path.partition("?")
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method.upper(),
            "scheme": "http",
            "path": route,
            "raw_path": route.encode(),
            "query_string": query.encode(),
            "root_path": "",
            "headers": [(b"host", b"gusteau.local"), (b"content-type", b"application/json")],
            "server": ("gusteau.local", 80),
            "client": ("gusteau.local", 0),
        }
        await self.app(scope, receive, send)

        start = next(m for m in messages if m["type"] == "http.response.start")
        headers = {k.decode().lower(): v.decode() for k, v in start.get("headers", [])}
        content = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
        return {
            "status": start["status"],
            "content_type": headers.get("content-type", ""),
            "body": content.decode("utf-8"),
        }

    async def request_json(self, method: str, path: str, body: str | None = None) -> str:
        """`request` for JavaScript, as JSON: {response, persist}, `persist` being the snapshot after a write."""
        response = await self.request(method, path, body)
        persist = None if method.upper() in READ_ONLY else self.snapshot()
        return json.dumps({"response": response, "persist": persist})

    def snapshot_json(self) -> str:
        return json.dumps(self.snapshot())
