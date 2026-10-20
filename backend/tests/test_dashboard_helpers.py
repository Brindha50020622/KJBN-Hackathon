from datetime import UTC, date, datetime

import pytest

from app.dashboard import complete_payment_split, ist_range_to_utc, return_rate_percent


def test_single_ist_day_becomes_a_utc_range():
    start, end = ist_range_to_utc(date(2026, 10, 11), date(2026, 10, 11))
    assert start == datetime(2026, 10, 10, 18, 30, tzinfo=UTC)
    assert end == datetime(2026, 10, 11, 18, 30, tzinfo=UTC)


def test_no_dates_means_no_limits():
    assert ist_range_to_utc(None, None) == (None, None)


def test_only_one_end_given():
    start, end = ist_range_to_utc(date(2026, 10, 11), None)
    assert start is not None
    assert end is None


def test_from_after_to_is_rejected():
    with pytest.raises(ValueError):
        ist_range_to_utc(date(2026, 10, 12), date(2026, 10, 11))


@pytest.mark.parametrize("bad", [date(1999, 12, 31), date(2101, 1, 1)])
def test_dates_outside_supported_years_are_rejected(bad):
    with pytest.raises(ValueError):
        ist_range_to_utc(bad, None)
    with pytest.raises(ValueError):
        ist_range_to_utc(None, bad)


@pytest.mark.parametrize(
    "returned,sold,rate",
    [(0, 0, 0.0), (0, 5, 0.0), (1, 6, 16.67), (1, 3, 33.33), (2, 3, 66.67), (3, 3, 100.0)],
)
def test_return_rate_percent(returned, sold, rate):
    assert return_rate_percent(returned, sold) == rate


def test_payment_split_lists_all_modes_in_fixed_order():
    result = complete_payment_split({"UPI": (900, 2)})
    assert result == [("CASH", 0, 0), ("UPI", 900, 2), ("CARD", 0, 0)]
