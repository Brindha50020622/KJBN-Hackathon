from datetime import UTC, datetime

import pytest

from tests.helpers import csv_bytes

CLOCK = {"X-Test-Clock": "2026-10-18T12:00:00+05:30"}


def row(tid, store, at, sku, name, qty, price, discount, mode, orig=""):
    return f"{tid},{store},{at},{sku},{name},{qty},{price},{discount},{mode},{orig}"


SEED = [
    row("T-1", "ST01", "2026-10-10 10:00:00", "SKU-1", "Rice 1kg", 4, "100.00", "0.00", "CASH"),
    row("T-2", "ST01", "2026-10-11 10:00:00", "SKU-2", "Dal 1kg", 2, "50.00", "10.00", "UPI"),
    # 02:00 IST on the 11th is still the 10th in UTC
    row("T-3", "ST03", "2026-10-11 02:00:00", "SKU-1", "Rice 1kg", 1, "100.00", "0.00", "CARD"),
    row(
        "R-1",
        "ST01",
        "2026-10-11 12:00:00",
        "SKU-1",
        "Rice 1kg",
        -1,
        "100.00",
        "0.00",
        "CASH",
        "T-1",
    ),
]


def upload(client, rows, name="seed.csv"):
    response = client.post(
        "/api/v1/batches", files={"file": (name, csv_bytes(*rows), "text/csv")}, headers=CLOCK
    )
    assert response.status_code == 202
    return response


@pytest.fixture
def loaded(client):
    upload(client, SEED)
    return client


def ids(client, **params):
    response = client.get("/api/v1/transactions", params=params)
    assert response.status_code == 200
    return [item["transaction_id"] for item in response.json()["items"]]


# ---- transactions ----


def test_list_is_newest_first(loaded):
    assert ids(loaded) == ["R-1", "T-2", "T-3", "T-1"]


def test_item_has_paise_utc_and_ist_time(loaded):
    item = loaded.get("/api/v1/transactions", params={"q": "T-2"}).json()["items"][0]
    assert (item["unit_price_paise"], item["discount_paise"], item["line_total_paise"]) == (
        5000,
        1000,
        9000,
    )
    assert item["sold_at_ist"] == "2026-10-11 10:00:00"
    assert datetime.fromisoformat(item["sold_at"]) == datetime(2026, 10, 11, 4, 30, tzinfo=UTC)
    assert item["store_code"] == "ST01"


def test_filter_by_store(loaded):
    assert ids(loaded, store="ST03") == ["T-3"]


def test_unknown_store_gives_empty_list(loaded):
    assert ids(loaded, store="ST99") == []


def test_filter_by_sku(loaded):
    assert ids(loaded, sku="SKU-2") == ["T-2"]


def test_returns_only(loaded):
    assert ids(loaded, returns_only="true") == ["R-1"]


def test_date_filter_uses_ist_days(loaded):
    assert ids(loaded, date_from="2026-10-10", date_to="2026-10-10") == ["T-1"]
    assert ids(loaded, date_from="2026-10-11", date_to="2026-10-11") == ["R-1", "T-2", "T-3"]
    assert ids(loaded, date_from="2026-10-11") == ["R-1", "T-2", "T-3"]


def test_search_text_matches_id_or_product_name_ignoring_case(loaded):
    assert ids(loaded, q="t-2") == ["T-2"]
    assert ids(loaded, q="dal") == ["T-2"]


def test_search_wildcards_are_plain_characters(loaded):
    assert ids(loaded, q="%") == []
    assert ids(loaded, q="_") == []


def test_search_text_cannot_inject_sql(loaded):
    assert ids(loaded, q="'; DROP TABLE transactions;--") == []
    assert len(ids(loaded)) == 4


def test_pagination(loaded):
    body = loaded.get("/api/v1/transactions", params={"limit": 2, "offset": 2}).json()
    assert body["total"] == 4
    assert [i["transaction_id"] for i in body["items"]] == ["T-3", "T-1"]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 201}, {"offset": -1}])
def test_bad_paging_is_422(client, params):
    assert client.get("/api/v1/transactions", params=params).status_code == 422


def test_date_from_after_date_to_is_rejected(client):
    response = client.get(
        "/api/v1/transactions", params={"date_from": "2026-10-12", "date_to": "2026-10-11"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


@pytest.mark.parametrize("value", ["abc", "2026-13-01", "1999-12-31"])
def test_bad_dates_are_422(client, value):
    response = client.get("/api/v1/transactions", params={"date_from": value})
    assert response.status_code == 422


# ---- dashboard ----


def dash(client, **params):
    response = client.get("/api/v1/dashboard", params=params)
    assert response.status_code == 200
    return response.json()


def test_totals_are_net_of_returns(loaded):
    body = dash(loaded)
    assert (body["total_revenue_paise"], body["total_transactions"]) == (49000, 4)


def test_revenue_by_day_uses_ist_days(loaded):
    days = [(d["day"], d["revenue_paise"]) for d in dash(loaded)["revenue_by_day"]]
    assert days == [("2026-10-10", 40000), ("2026-10-11", 9000)]


def test_revenue_by_store_lists_all_six_stores(loaded):
    stores = {s["store_code"]: s for s in dash(loaded)["revenue_by_store"]}
    assert sorted(stores) == ["ST01", "ST02", "ST03", "ST04", "ST05", "ST06"]
    assert (stores["ST01"]["revenue_paise"], stores["ST01"]["transactions"]) == (39000, 3)
    assert (stores["ST03"]["revenue_paise"], stores["ST03"]["transactions"]) == (10000, 1)
    assert stores["ST02"]["revenue_paise"] == 0


def test_top_products_by_net_quantity(loaded):
    products = [(p["sku"], p["net_quantity"]) for p in dash(loaded)["top_products"]]
    assert products == [("SKU-1", 4), ("SKU-2", 2)]


def test_top_products_is_limited_to_ten(client):
    rows = [
        row(
            f"P-{i}",
            "ST01",
            "2026-10-10 10:00:00",
            f"SKU-{i:02d}",
            f"Item {i}",
            i + 1,
            "10.00",
            "0.00",
            "CASH",
        )
        for i in range(12)
    ]
    upload(client, rows)
    skus = [p["sku"] for p in dash(client)["top_products"]]
    assert skus == [f"SKU-{i:02d}" for i in range(11, 1, -1)]


def test_return_rate_by_store(loaded):
    rates = {r["store_code"]: r for r in dash(loaded)["return_rate_by_store"]}
    assert (rates["ST01"]["sold_quantity"], rates["ST01"]["returned_quantity"]) == (6, 1)
    assert rates["ST01"]["return_rate_percent"] == 16.67
    assert rates["ST03"]["return_rate_percent"] == 0.0
    assert rates["ST02"]["return_rate_percent"] == 0.0


def test_payment_split(loaded):
    split = {
        p["payment_mode"]: (p["revenue_paise"], p["transactions"])
        for p in dash(loaded)["payment_split"]
    }
    assert split == {"CASH": (30000, 2), "UPI": (9000, 1), "CARD": (10000, 1)}


def test_dashboard_date_range_boundaries(loaded):
    first = dash(loaded, date_from="2026-10-10", date_to="2026-10-10")
    assert (first["total_revenue_paise"], first["total_transactions"]) == (40000, 1)
    second = dash(loaded, date_from="2026-10-11", date_to="2026-10-11")
    assert (second["total_revenue_paise"], second["total_transactions"]) == (9000, 3)


def test_date_range_with_no_data_returns_empty_dashboard(loaded):
    body = dash(loaded, date_from="2025-01-01", date_to="2025-01-02")
    assert (body["total_revenue_paise"], body["total_transactions"]) == (0, 0)
    assert body["revenue_by_day"] == []
    assert body["top_products"] == []
    assert len(body["revenue_by_store"]) == 6
    assert all(r["return_rate_percent"] == 0.0 for r in body["return_rate_by_store"])
    assert [p["revenue_paise"] for p in body["payment_split"]] == [0, 0, 0]


def test_dashboard_on_empty_database(client):
    body = dash(client)
    assert body["total_revenue_paise"] == 0
    assert body["revenue_by_day"] == []


def test_dashboard_rejects_bad_ranges(client):
    response = client.get(
        "/api/v1/dashboard", params={"date_from": "2026-10-12", "date_to": "2026-10-11"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert client.get("/api/v1/dashboard", params={"date_to": "nope"}).status_code == 422
