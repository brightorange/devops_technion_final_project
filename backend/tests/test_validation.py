from decimal import Decimal

import pytest

from app.validation import is_int, to_price


@pytest.mark.parametrize(
    "value, expected",
    [
        (10, Decimal("10")),
        (19.99, Decimal("19.99")),
        (0.01, Decimal("0.01")),
        (99999999.99, Decimal("99999999.99")),
    ],
)
def test_to_price_accepts_valid_prices(value, expected):
    assert to_price(value) == expected


@pytest.mark.parametrize(
    "value",
    [0, -5, 1.234, 100000000, float("nan"), float("inf"), "10", None, True],
)
def test_to_price_rejects_invalid_prices(value):
    assert to_price(value) is None


@pytest.mark.parametrize("value, expected", [(1, True), (0, True), (True, False), (1.0, False)])
def test_is_int(value, expected):
    assert is_int(value) is expected
