import math

import pytest

from open_assessor.domain.expenses.money import MAX_AMOUNT_CENTS, format_brl, to_cents


class TestToCents:
    def test_converts_decimals_to_integer_cents(self):
        assert to_cents(50) == 5000
        assert to_cents(50.9) == 5090

    def test_does_not_suffer_from_float_drift(self):
        assert to_cents(19.99) == 1999
        assert to_cents(0.07) == 7

    def test_rounds_half_up_like_javascript(self):
        assert to_cents(0.125) == 13

    @pytest.mark.parametrize("value", [0, -5, math.nan, math.inf, "50", None, True])
    def test_rejects_non_positive_non_finite_and_non_number_values(self, value: object):
        assert to_cents(value) is None

    def test_rejects_amounts_that_round_to_zero(self):
        assert to_cents(0.004) is None

    def test_rejects_amounts_above_the_cap(self):
        assert to_cents(MAX_AMOUNT_CENTS / 100) == MAX_AMOUNT_CENTS
        assert to_cents(MAX_AMOUNT_CENTS / 100 + 0.01) is None


class TestFormatBrl:
    def test_formats_cents_with_a_decimal_comma_and_thousands_dot(self):
        assert format_brl(5090) == "R$ 50,90"
        assert format_brl(123456) == "R$ 1.234,56"
        assert format_brl(100_000_000) == "R$ 1.000.000,00"
