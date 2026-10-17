"""Prepare the mobile build's public dir, public-mobile/ (git-ignored; run before `dev:mobile`/`build:mobile`).

It is public/ plus pyodide/ with:

- Pyodide core files, copied from node_modules/pyodide (the version pinned in package.json)
- the backend's dependencies: wheels from the Pyodide repository (compiled ones like pydantic-core and SQLAlchemy
  must come from there) plus pure-Python wheels from PyPI at the versions pinned in uv.lock; sha256-checked and
  cached in .pyodide-cache/, so only the first run needs the network
- gusteau.zip: the backend package, bundled recipes, aisles and products, unpacked into the worker's file system

Python files are precompiled to bytecode (unchecked hash-based .pyc, so the source is never re-read): Pyodide's
stdlib and the wheels ship sources only, and compiling them on every launch was over half of the boot time. That
needs this interpreter to match Pyodide's Python version, hence `uv run` (the project's Python) in package.json.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import marshal
import shutil
import struct
import sys
import tomllib
import urllib.request
import zipfile
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent
ROOT = FRONTEND.parent
NODE_PYODIDE = FRONTEND / "node_modules" / "pyodide"
PUBLIC = FRONTEND / "public"
PUBLIC_MOBILE = FRONTEND / "public-mobile"  # vite's publicDir in --mode mobile
OUT = PUBLIC_MOBILE / "pyodide"
CACHE = FRONTEND / ".pyodide-cache"  # downloads, as published

CORE = ["pyodide.asm.mjs", "pyodide.asm.wasm"]
# from the Pyodide repository; their dependencies are resolved from pyodide-lock.json
PYODIDE_PACKAGES = ["fastapi", "sqlalchemy", "pyyaml", "markupsafe", "pyodide-http"]
# pure Python, not in the Pyodide repository: from PyPI at the uv.lock version
PYPI_PACKAGES = ["alembic", "mako"]
# backend code and data shipped inside the app
APP_FILES = ["gusteau", "recipes", "aisles.yml", "products.yml"]

# where Pyodide puts things: only used for file names in tracebacks
SITE_PACKAGES = "/lib/python3.14/site-packages/"
STDLIB_ZIP = "/lib/python314.zip/"
APP_DIR = "/app/"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str, dest: Path, digest: str) -> bytes:
    if dest.exists() and sha256(data := dest.read_bytes()) == digest:
        return data
    print(f"  downloading {dest.name}")
    with urllib.request.urlopen(url, timeout=60) as res:
        data = res.read()
    if sha256(data) != digest:
        sys.exit(f"sha256 mismatch for {url}")
    dest.write_bytes(data)
    return data


class Compiler:
    """Adds bytecode next to the sources of a zip (a wheel, the stdlib, the app bundle)."""

    def __init__(self, enabled: bool):
        self.enabled = enabled

    def pyc(self, source: bytes, filename: str) -> bytes | None:
        try:
            code = compile(source, filename, "exec", dont_inherit=True)
        except SyntaxError:  # e.g. stdlib test data that is invalid on purpose
            return None
        # PEP 552: flags=0b01 -> hash-based and unchecked, so the import system never compares it with the source
        return (
            importlib.util.MAGIC_NUMBER
            + struct.pack("<I", 0b01)
            + importlib.util.source_hash(source)
            + marshal.dumps(code)
        )

    def zip(self, data: bytes, prefix: str, beside: bool = False) -> bytes:
        """`beside`: x.pyc next to x.py (what zipimport looks for) instead of __pycache__/x.cpython-314.pyc."""
        if not self.enabled:
            return data
        out = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
            names = set(src.namelist())
            for info in src.infolist():
                content = src.read(info)
                dst.writestr(info, content)
                if not info.filename.endswith(".py"):
                    continue
                parent, _, module = info.filename.rpartition("/")
                stem = module[:-3]
                pyc_name = (
                    f"{parent}/{stem}.pyc".lstrip("/")
                    if beside
                    else f"{parent}/__pycache__/{stem}.{sys.implementation.cache_tag}.pyc".lstrip("/")
                )
                if pyc_name not in names and (pyc := self.pyc(content, prefix + info.filename)):
                    dst.writestr(pyc_name, pyc)
        return out.getvalue()


def pyodide_wheels(lock: dict, version: str, compiler: Compiler) -> list[str]:
    packages = lock["packages"]
    todo, seen = list(PYODIDE_PACKAGES), set()
    while todo:
        name = todo.pop().lower().replace("_", "-")
        if name in seen:
            continue
        seen.add(name)
        todo += packages[name].get("depends", [])
    for name in sorted(seen):
        info = packages[name]
        url = f"https://cdn.jsdelivr.net/pyodide/v{version}/full/{info['file_name']}"
        wheel = compiler.zip(download(url, CACHE / info["file_name"], info["sha256"]), SITE_PACKAGES)
        (OUT / info["file_name"]).write_bytes(wheel)
        info["sha256"] = sha256(wheel)  # the loader checks integrity against the served lock file
    return sorted(seen)


def pypi_wheels(compiler: Compiler) -> list[str]:
    pinned = {p["name"]: p["version"] for p in tomllib.loads((ROOT / "uv.lock").read_text())["package"]}
    files = []
    for name in PYPI_PACKAGES:
        version = pinned[name]
        cached = [p for p in CACHE.glob("*-py3-none-any.whl") if p.name.lower().startswith(f"{name}-{version}-")]
        if cached:  # pinned version already downloaded (and checked): no need for the network
            filename, data = cached[0].name, cached[0].read_bytes()
        else:
            with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=30) as res:
                meta = json.load(res)
            wheel = next(u for u in meta["urls"] if u["filename"].endswith("-py3-none-any.whl"))
            filename = wheel["filename"]
            data = download(wheel["url"], CACHE / filename, wheel["digests"]["sha256"])
        (OUT / filename).write_bytes(compiler.zip(data, SITE_PACKAGES))
        files.append(filename)
    return files


def app_bundle(compiler: Compiler) -> None:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in APP_FILES:
            src = ROOT / name
            paths = [src] if src.is_file() else sorted(p for p in src.rglob("*") if p.is_file())
            for path in paths:
                rel = path.relative_to(ROOT)
                if "__pycache__" in rel.parts or rel.parts[:2] == ("gusteau", "static") or path.suffix == ".pyc":
                    continue
                zf.write(path, rel.as_posix())
    (OUT / "gusteau.zip").write_bytes(compiler.zip(out.getvalue(), APP_DIR))


def main() -> None:
    if not NODE_PYODIDE.is_dir():
        sys.exit("node_modules/pyodide missing: run `npm install` first")
    version = json.loads((NODE_PYODIDE / "package.json").read_text())["version"]
    lock = json.loads((NODE_PYODIDE / "pyodide-lock.json").read_text())
    pyodide_python = tuple(int(x) for x in lock["info"]["python"].split(".")[:2])
    compiler = Compiler(enabled=sys.version_info[:2] == pyodide_python)
    print(f"Pyodide {version} (Python {lock['info']['python']})")
    if not compiler.enabled:
        print(f"  warning: Python {sys.version.split()[0]} can't precompile for {lock['info']['python']}: slower boot")

    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(exist_ok=True)
    shutil.copytree(
        PUBLIC, PUBLIC_MOBILE, dirs_exist_ok=True
    )  # the web app's public files (manifest, icons) come along
    for name in CORE:
        shutil.copy2(NODE_PYODIDE / name, OUT / name)
    stdlib = (NODE_PYODIDE / "python_stdlib.zip").read_bytes()
    (OUT / "python_stdlib.zip").write_bytes(compiler.zip(stdlib, STDLIB_ZIP, beside=True))

    packages = pyodide_wheels(lock, version, compiler)
    (OUT / "pyodide-lock.json").write_text(json.dumps(lock))
    wheels = pypi_wheels(compiler)
    app_bundle(compiler)
    manifest = {"pyodide": version, "packages": packages, "wheels": wheels, "app": "gusteau.zip"}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    size = sum(p.stat().st_size for p in OUT.iterdir()) / 1e6
    print(f"public-mobile/pyodide ready: {len(packages)} packages + {len(wheels)} wheels, {size:.1f} MB")


if __name__ == "__main__":
    main()
