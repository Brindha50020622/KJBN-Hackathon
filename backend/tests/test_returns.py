from datetime import UTC, datetime

from app.rules import TxnInfo, check_return

SOLD = datetime(2026, 10, 11, 9, 0, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 11, 12, 0, 0, tzinfo=UTC)
ORIGINAL = TxnInfo("T-91", "ST03", "SKU-114", 3, SOLD)


def check(quantity=-1, store="ST03", sku="SKU-114", sold_at=LATER, original=ORIGINAL, returned=0):
    return check_return(quantity, store, sku, sold_at, original, returned)


def test_valid_return_passes():
    assert check() is None


def test_original_must_exist():
    assert check(original=None) is not None


def test_original_must_be_from_same_store():
    assert check(store="ST01") is not None


def test_original_must_have_same_sku():
    assert check(sku="SKU-201") is not None


def test_cannot_return_a_return():
    original = TxnInfo("T-92", "ST03", "SKU-114", -1, SOLD)
    assert check(original=original) is not None


def test_return_dated_before_original_is_rejected():
    assert check(sold_at=datetime(2026, 10, 11, 8, 59, 59, tzinfo=UTC)) is not None


def test_return_total_equal_to_original_quantity_is_accepted():
    assert check(quantity=-1, returned=2) is None


def test_return_total_over_original_quantity_is_rejected():
    assert check(quantity=-1, returned=3) is not None


def test_single_return_larger_than_original_is_rejected():
    assert check(quantity=-4) is not None
