import pytest

from gusteau.store import Store

from .conftest import WEEK


@pytest.fixture
def planned(client):
    days = {
        "lunes": {"desayuno": "tortilla-francesa-pan", "comida": "lentejas-con-verduras", "cena": "tortilla-patatas"},
        "martes": {"desayuno": None, "comida": "lentejas-con-verduras", "cena": None},
    }
    assert client.put(f"/api/plans/{WEEK}", json={"days": days}).status_code == 200
    return client


def outcome(client, day, slot, **body):
    return client.put(f"/api/plans/{WEEK}/meals/{day}/{slot}/outcome", json=body)


def test_meal_outcomes(planned):
    assert planned.get(f"/api/plans/{WEEK}").json()["outcomes"] == {}  # default: cooked as planned

    r = outcome(planned, "lunes", "cena", status="swapped", swap_title="  pizza fuera ")
    assert r.status_code == 200
    assert r.json()["outcomes"]["lunes"]["cena"] == {
        "status": "swapped",
        "swap_slug": None,
        "swap_title": "pizza fuera",
    }

    r = outcome(planned, "martes", "comida", status="swapped", swap_slug="tortilla-patatas")
    assert r.json()["outcomes"]["martes"]["comida"]["swap_title"] == "Tortilla de patatas"

    outcome(planned, "lunes", "comida", status="skipped")
    outcome(planned, "lunes", "cena", status="cooked")  # back to default
    out = planned.get(f"/api/plans/{WEEK}").json()["outcomes"]
    assert out["lunes"] == {"comida": {"status": "skipped", "swap_slug": None, "swap_title": None}}


def test_outcome_validation(planned):
    assert outcome(planned, "martes", "cena", status="skipped").status_code == 404  # empty slot
    assert outcome(planned, "lunes", "cena", status="swapped").status_code == 422  # swapped for what?
    assert outcome(planned, "lunes", "cena", status="swapped", swap_slug="no-existe").status_code == 404
    assert outcome(planned, "lunes", "cena", status="eaten").status_code == 422


def test_replanning_a_slot_resets_its_outcome_but_keeps_others(planned):
    outcome(planned, "lunes", "comida", status="skipped")
    outcome(planned, "lunes", "cena", status="skipped")
    plan = planned.get(f"/api/plans/{WEEK}").json()
    plan["days"]["lunes"]["cena"] = "lentejas-con-verduras"
    out = planned.put(f"/api/plans/{WEEK}", json={"days": plan["days"]}).json()["outcomes"]
    assert set(out["lunes"]) == {"comida"}


def test_purchase_snapshot_keeps_prices_and_receipt(planned):
    r = planned.post(f"/api/plans/{WEEK}/purchases")
    assert r.status_code == 201
    p = r.json()
    assert p["people"] == 2 and p["actual_total"] is None
    assert p["created_at"].endswith("Z")  # timezone survives the SQLite round trip
    assert planned.get("/api/purchases").json()[0]["created_at"] == p["created_at"]
    shopping = planned.get(f"/api/plans/{WEEK}/shopping").json()
    assert p["estimated_total"] == shopping["total"]
    eggs = next(i for i in p["items"] if i["name"] == "huevos")
    assert eggs["product_id"] == "31504" and eggs["cost"] > 0

    r = planned.patch(f"/api/purchases/{p['id']}", json={"actual_total": 87.4})
    assert r.json()["actual_total"] == 87.4
    assert [x["id"] for x in planned.get("/api/purchases", params={"week": WEEK}).json()] == [p["id"]]
    assert planned.delete(f"/api/purchases/{p['id']}").status_code == 204
    assert planned.get("/api/purchases").json() == []


def test_purchase_needs_a_plan(client):
    assert client.post("/api/plans/2026-W30/purchases").status_code == 409
    assert client.patch("/api/purchases/999", json={"actual_total": 1}).status_code == 404


def test_migrations_upgrade_and_downgrade(tmp_path):
    from alembic import command

    from gusteau.db import alembic_config

    store = Store(tmp_path)
    cfg = alembic_config(store.engine)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
