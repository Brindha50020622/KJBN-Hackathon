from datetime import UTC, datetime

import pytest

from app.rules import (
    REQUIRED_COLUMNS,
    HeaderError,
    line_total_paise,
    parse_money_to_paise,
    parse_sold_at,
    validate_header,
)


@pytest.mark.parametrize(
    "text,paise", [("540.00", 54000), ("540.5", 54050), ("540", 54000), ("0", 0), ("0.01", 1)]
)
def test_parse_money_ok(text, paise):
    assert parse_money_to_paise(text) == paise


@pytest.mark.parametrize("text", ["-1", "abc", "", "540.001", "1e3"])
def test_parse_money_rejects_bad_values(text):
    with pytest.raises(ValueError):
        parse_money_to_paise(text)


def test_line_total_for_sale():
    assert line_total_paise(2, 54000, 4000) == 104000


def test_line_total_for_return_without_discount():
    assert line_total_paise(-1, 54000, 0) == -54000


def test_line_total_for_return_gives_discount_back():
    assert line_total_paise(-1, 54000, 4000) == -50000


def test_sold_at_is_read_as_ist_and_stored_as_utc():
    assert parse_sold_at("2026-10-11 14:32:10") == datetime(2026, 10, 11, 9, 2, 10, tzinfo=UTC)


@pytest.mark.parametrize("text", ["11-10-2026 14:32:10", "2026-10-11T14:32:10", "2026-10-11", ""])
def test_sold_at_rejects_wrong_format(text):
    with pytest.raises(ValueError):
        parse_sold_at(text)


def test_header_with_all_columns_is_ok():
    validate_header(REQUIRED_COLUMNS)


def test_header_with_different_order_is_ok():
    validate_header(list(reversed(REQUIRED_COLUMNS)))


def test_header_with_extra_column_is_ok():
    validate_header([*REQUIRED_COLUMNS, "cashier"])


@pytest.mark.parametrize("missing", REQUIRED_COLUMNS)
def test_header_missing_any_column_rejects_file(missing):
    with pytest.raises(HeaderError):
        validate_header([c for c in REQUIRED_COLUMNS if c != missing])


def test_empty_header_rejects_file():
    with pytest.raises(HeaderError):
        validate_header([])