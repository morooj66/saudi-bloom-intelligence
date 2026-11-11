"""Unit tests for parsers. Inline strings below are tiny parser fixtures (NOT data) written to exercise formats."""
import math

import pytest

from bloom.regions import ISO_CODES, standardize_region
from bloom.trends_io import clean_cell, parse_date, parse_term_header, parse_value, parse_window


@pytest.mark.parametrize("raw,val,cens,bound,miss", [
    ("12", 12, False, None, False),
    ("87‎%‎", 87, False, None, False),
    ("<1", None, True, 1, False),
    ("أقل من 1", None, True, 1, False),
    ("أقل من 1%", None, True, 1, False),
    ("", None, False, None, True),
    ("٣٤", 34, False, None, False),
])
def test_parse_value(raw, val, cens, bound, miss):
    c = parse_value(raw)
    assert c.censored is cens and c.missing is miss
    if val is None:
        assert math.isnan(c.value)  # censored/missing are never turned into numbers
    else:
        assert c.value == val
    if bound is not None:
        assert c.upper_bound == bound


def test_parse_value_rejects_garbage():
    with pytest.raises(ValueError):
        parse_value("N/A")


def test_clean_cell_strips_bidi():
    assert clean_cell("‏منطقة‎ ") == "منطقة"


def test_term_header_and_window():
    assert parse_term_header("ورد: (المملكة العربية السعودية)") == ("ورد", "المملكة العربية السعودية")
    ws, we = parse_window("10‏/11‏/2021 - 10‏/11‏/2026")
    assert (ws.day, ws.month, ws.year) == (10, 11, 2021) and (we.year, we.month) == (2026, 11)
    with pytest.raises(ValueError):
        parse_term_header("no colon")


def test_parse_date_weekly_and_monthly_and_invalid():
    assert parse_date("2021-11-07").day == 7
    assert parse_date("2021-11").day == 1
    with pytest.raises(ValueError):
        parse_date("07/11/2021")


@pytest.mark.parametrize("name", ["منطقة الرياض", "القصيم", "مكة المكرمة", "المنطقة الشرقية", "منطقة المدينة", "جازان", "منطقة الحدود الشمالية", "منطقة الباحة"])
def test_region_aliases(name):
    assert standardize_region(name)[0] in ISO_CODES


def test_unknown_region_raises():
    with pytest.raises(ValueError):
        standardize_region("دبي")


def test_thirteen_unique_regions():
    assert len(set(ISO_CODES)) == 13
