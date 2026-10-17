import asyncio
import json
from typing import Any

import pytest

from gusteau.mobile import MobileApp

from .conftest import WEEK


def call(app: MobileApp, method: str, path: str, body=None) -> tuple[int, Any]:
    res = asyncio.run(app.request(method, path, json.dumps(body) if body is not None else None))
    assert res["content_type"].startswith("application/json") or res["status"] == 204, res
    return res["status"], json.loads(res["body"]) if res["body"] else None


def test_serves_the_api_in_process(tmp_path):
    app = MobileApp(tmp_path)
    status, recipes = call(app, "GET", "/api/recipes")
    assert status == 200 and recipes

    status, plan = call(app, "POST", f"/api/plans/{WEEK}/generate", {"seed": 1})
    assert status == 200 and all(v for day in plan["days"].values() for v in day.values())

    status, settings = call(app, "PUT", "/api/settings", {"people": 3})
    assert status == 200 and settings["people"] == 3
    assert call(app, "GET", "/api/settings")[1]["people"] == 3  # persisted in the data dir


def test_errors_and_query_strings(tmp_path):
    app = MobileApp(tmp_path)
    status, body = call(app, "GET", "/api/recipes/no-existe")
    assert status == 404 and "no-existe" in body["detail"]
    assert call(app, "GET", "/api/plans/bad-week")[0] == 422
    status, _ = call(app, "GET", f"/api/plans/{WEEK}/shopping?people=4&prices=false")
    assert status == 200


def test_non_json_responses(tmp_path):
    app = MobileApp(tmp_path)
    res = asyncio.run(app.request("GET", f"/api/plans/{WEEK}/shopping.md?prices=false"))
    assert res["status"] == 200 and res["content_type"].startswith("text/plain") and res["body"].startswith("#")


def test_only_answers_the_api(tmp_path):
    assert asyncio.run(MobileApp(tmp_path).request("GET", "/"))["status"] == 404  # no SPA mounted


def saved_after_boot(tmp_path) -> tuple[MobileApp, dict[str, str]]:
    """A fresh app and what the phone would have stored after its first start."""
    app = MobileApp(tmp_path / "first")
    return app, app.snapshot()["changed"]


def test_first_snapshot_has_the_whole_data_dir(tmp_path):
    _, files = saved_after_boot(tmp_path)
    assert {"gusteau.db", "aisles.yml", ".seeded.json"} <= set(files)
    assert any(f.startswith("recipes/") and f.endswith(".cook") for f in files)
    assert not any(f.endswith(("-wal", "-shm")) or f.startswith(".cache/") for f in files)


def test_restores_from_saved_files_and_reports_only_changes(tmp_path):
    first, files = saved_after_boot(tmp_path)
    call(first, "PUT", "/api/settings", {"people": 4})
    files |= first.snapshot()["changed"]  # the app stores what changed

    app = MobileApp(tmp_path / "phone", files)  # next launch: rebuilt from storage
    assert call(app, "GET", "/api/settings")[1]["people"] == 4
    assert app.snapshot() == {"changed": {}, "deleted": []}  # nothing new to store

    reply = json.loads(asyncio.run(app.request_json("PUT", "/api/settings", json.dumps({"people": 5}))))
    assert reply["response"]["status"] == 200 and set(reply["persist"]["changed"]) == {"gusteau.db"}
    assert json.loads(asyncio.run(app.request_json("GET", "/api/settings")))["persist"] is None  # reads don't snapshot


def test_reports_deleted_files(tmp_path):
    app, _ = saved_after_boot(tmp_path)
    slug = call(app, "GET", "/api/recipes")[1][0]["slug"]
    assert call(app, "DELETE", f"/api/recipes/{slug}")[0] == 204
    assert app.snapshot()["deleted"] == [f"recipes/{slug}.cook"]


def test_rejects_paths_outside_the_data_dir(tmp_path):
    with pytest.raises(ValueError):
        MobileApp(tmp_path / "data", {"../escape.txt": ""})
