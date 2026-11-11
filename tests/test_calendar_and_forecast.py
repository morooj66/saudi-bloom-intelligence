import numpy as np
import pandas as pd
import pytest

from bloom.calendar_features import EVENT_VERIFICATION, build_weekly_calendar, event_dates
from bloom.forecast import FEATURE_COLS, predict_from_origin


def test_islamic_dates_not_fixed_gregorian():
    ev = event_dates(2022, 2026)
    f = ev[ev["event"] == "eid_al_fitr"].set_index(ev[ev["event"] == "eid_al_fitr"]["date"].dt.year)["date"]
    assert f[2022].strftime("%m-%d") != f[2025].strftime("%m-%d")
    assert (f[2022] - f[2023]).days != 0


def test_umm_al_qura_matches_every_verified_announcement():
    ev = event_dates(2021, 2027)
    for (name, iso), _src in EVENT_VERIFICATION.items():
        assert ((ev["event"] == name) & (ev["date"] == pd.Timestamp(iso))).any(), (name, iso)


def test_known_event_weeks():
    cal = build_weekly_calendar(pd.date_range("2025-03-23", periods=3, freq="7D"))
    assert cal.loc[cal["week_start"] == "2025-03-30", "eid_al_fitr_in_week"].item()
    assert cal.loc[cal["week_start"] == "2025-03-23", "eid_al_fitr_week_offset"].item() == 1


def test_calendar_depends_only_on_dates():
    a = build_weekly_calendar(pd.date_range("2024-01-07", periods=60, freq="7D"))
    b = build_weekly_calendar(pd.date_range("2024-01-07", periods=30, freq="7D"))
    pd.testing.assert_frame_equal(a.iloc[:30].reset_index(drop=True), b.reset_index(drop=True))  # adding future dates changes nothing
    assert a["known_in_advance"].all()


def test_forecast_never_reads_future_values():
    rng = np.random.default_rng(1)  # synthetic arrays used ONLY to test leakage mechanics, never as data
    y = rng.uniform(20, 60, 200)
    cal = build_weekly_calendar(pd.date_range("2022-01-02", periods=210, freq="7D"))
    origin, h = 160, 3
    base = predict_from_origin(y, cal, origin, h)
    y2 = y.copy(); y2[origin + 1:] = 1e6  # corrupt everything after the origin
    assert predict_from_origin(y2, cal, origin, h) == base
    y3 = y.copy(); y3[origin + 1:] = np.nan
    assert predict_from_origin(y3, cal, origin, h) == base


def test_feature_columns_exist():
    cal = build_weekly_calendar(pd.date_range("2024-01-07", periods=10, freq="7D"))
    assert set(FEATURE_COLS) <= set(cal.columns)
