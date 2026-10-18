from datetime import UTC, datetime

import pytest

from app.rules import validate_row

NOW = datetime(2026, 10, 18, 12, 0, 0, tzinfo=UTC)
STORES = {"ST01", "ST03"}


def make_row(**changes):
    row = {
        "transaction_id": "T-1",
        "store_code": "ST03",
        "sold_at": "2026-10-11 14:32:10",
        "sku": "SKU-114",
        "product_name": "Basmati Rice 5kg",
        "quantity": "2",
        "unit_price": "540.00",
        "discount": "40.00",
        "payment_mode": "UPI",
        "original_transaction_id": "",
    }
    row.update(changes)
    return row


def error_columns(**changes):
    return [e.column for e in validate_row(make_row(**changes), STORES, NOW)]


def test_valid_row_has_no_errors():
    assert validate_row(make_row(), STORES, NOW) == []


def test_missing_transaction_id():
    assert "transaction_id" in error_columns(transaction_id="")


def test_unknown_store_code():
    assert "store_code" in error_columns(store_code="ST99")


@pytest.mark.parametrize("qty", ["0", "1.5", "abc", ""])
def test_quantity_must_be_a_non_zero_integer(qty):
    assert "quantity" in error_columns(quantity=qty)


def test_unit_price_zero_is_allowed():
    assert error_columns(unit_price="0.00", discount="0.00") == []


def test_unit_price_negative_is_rejected():
    assert "unit_price" in error_columns(unit_price="-0.01")


@pytest.mark.parametrize("discount,ok", [("0.00", True), ("1080.00", True), ("1080.01", False)])
def test_discount_upper_boundary_for_sale(discount, ok):
    assert ("discount" not in error_columns(discount=discount)) is ok


def test_discount_negative_is_rejected():
    assert "discount" in error_columns(discount="-0.01")


@pytest.mark.parametrize("discount,ok", [("1080.00", True), ("1080.01", False)])
def test_discount_boundary_for_return_uses_absolute_quantity(discount, ok):
    cols = error_columns(quantity="-2", discount=discount, original_transaction_id="T-0")
    assert ("discount" not in cols) is ok


def test_return_without_original_transaction_id_is_rejected():
    assert "original_transaction_id" in error_columns(quantity="-1", discount="0.00")


@pytest.mark.parametrize("mode", ["WALLET", "cash", ""])
def test_payment_mode_must_be_cash_upi_or_card(mode):
    assert "payment_mode" in error_columns(payment_mode=mode)


@pytest.mark.parametrize("mode", ["CASH", "UPI", "CARD"])
def test_valid_payment_modes(mode):
    assert error_columns(payment_mode=mode) == []


@pytest.mark.parametrize("text", ["11-10-2026 14:32:10", "2026-10-11T14:32:10"])
def test_sold_at_wrong_format(text):
    assert "sold_at" in error_columns(sold_at=text)


def test_sold_at_one_second_in_the_future_is_rejected():
    # NOW is 12:00:00 UTC = 17:30:00 IST
    assert "sold_at" in error_columns(sold_at="2026-10-18 17:30:01")


def test_sold_at_exactly_now_is_accepted():
    assert "sold_at" not in error_columns(sold_at="2026-10-18 17:30:00")