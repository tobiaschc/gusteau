from .conftest import WEEK  # 2026-W40: Mon 28 Sep .. Sun 4 Oct 2026

THURSDAY = "2026-10-01"


def plan(client, week, days):
    assert client.put(f"/api/plans/{week}", json={"days": days}).status_code == 200


def stats(client, **params):
    r = client.get("/api/stats", params={"today": THURSDAY, **params})
    assert r.status_code == 200, r.text
    return r.json()


def test_counts_only_past_meals_and_follows_swaps(client):
    lentejas, tortilla, desayuno = "lentejas-con-verduras", "tortilla-patatas", "tortilla-francesa-pan"
    plan(client, "2026-W39", {"lunes": {"comida": lentejas, "cena": tortilla}, "domingo": {"comida": lentejas}})
    plan(
        client,
        WEEK,
        {
            "lunes": {"desayuno": desayuno, "comida": lentejas, "cena": tortilla},
            "martes": {"desayuno": desayuno, "cena": tortilla},
            "jueves": {"comida": lentejas},  # today: counts
            "viernes": {"comida": lentejas},  # future: doesn't
        },
    )
    put = lambda day, slot, **b: client.put(f"/api/plans/{WEEK}/meals/{day}/{slot}/outcome", json=b)
    put("martes", "cena", status="swapped", swap_title="Pizza fuera")
    put("lunes", "cena", status="skipped")

    s = stats(client)
    dishes = {d["title"]: d for d in s["dishes"]}
    assert dishes["Lentejas con verduras"]["count"] == 4  # W39 x2 + lunes + jueves
    assert dishes["Lentejas con verduras"]["last"] == THURSDAY
    assert dishes["Tortilla de patatas"]["count"] == 1  # W39 only: lunes skipped, martes swapped
    assert dishes["Pizza fuera"] == {"slug": None, "title": "Pizza fuera", "count": 1, "last": "2026-09-29"}
    assert s["dishes"][0]["title"] == "Lentejas con verduras"  # most eaten first
    assert [(b["slug"], b["count"]) for b in s["breakfasts"]] == [(desayuno, 2)]
    assert s["meals_eaten"] == 4 + 1 + 1 + 2 and s["meals_skipped"] == 1
    never = {r["slug"] for r in s["never_eaten"]}
    assert lentejas not in never and desayuno not in never and "merluza-salsa-verde" in never


def test_period_filter(client):
    plan(client, "2026-W30", {"lunes": {"comida": "lentejas-con-verduras"}})
    plan(client, WEEK, {"lunes": {"comida": "lentejas-con-verduras"}})
    assert stats(client, weeks=4)["dishes"][0]["count"] == 1
    assert stats(client, weeks=0)["dishes"][0]["count"] == 2
    assert stats(client, weeks=4)["since"] == "2026-W37"


def test_spending_uses_receipt_when_present(client):
    plan(client, "2026-W38", {"lunes": {"comida": "lentejas-con-verduras"}})
    plan(client, "2026-W39", {"lunes": {"comida": "lentejas-con-verduras"}})
    plan(client, WEEK, {"lunes": {"desayuno": "tortilla-francesa-pan"}})  # eggs + bread: priced by the fake shop
    assert client.post("/api/plans/2026-W38/purchases").json()["estimated_total"] is None  # no prices, no receipt
    a = client.post("/api/plans/2026-W39/purchases").json()
    b = client.post(f"/api/plans/{WEEK}/purchases").json()
    assert b["estimated_total"] > 0
    client.patch(f"/api/purchases/{a['id']}", json={"actual_total": 50})
    sp = stats(client)["spending"]
    assert [(w["week"], w["total"], w["exact"]) for w in sp["weeks"]] == [  # W38: nothing to count
        ("2026-W39", 50, True),
        (WEEK, b["estimated_total"], False),
    ]
    # W39 (Thu 24 Sep) -> September; W40 (Thu 1 Oct) -> October
    assert [m["month"] for m in sp["months"]] == ["2026-09", "2026-10"]
    assert sp["total"] == round(50 + b["estimated_total"], 2)
    assert sp["average_week"] == round(sp["total"] / 2, 2)


def test_empty(client):
    s = stats(client)
    assert s["dishes"] == [] and s["spending"] == {"weeks": [], "months": [], "total": None, "average_week": None}
