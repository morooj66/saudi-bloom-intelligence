"""Forecast acceptance gate + suppression. Arrays below are constructed ONLY to exercise gate arithmetic
(they are test fixtures, never data and never shown anywhere)."""
import json

import numpy as np
import pandas as pd
import pytest

from bloom import config as C
from bloom.forecast import GATE_MIN_IMPROVEMENT, HORIZONS, MIN_TRAIN, Backtest, compute_gate, forecast_future

Y = np.linspace(20, 60, 200)  # only used for the MASE scale


def frame(naive_ae, ols_ae, n_hz=4):
    rows = []
    for i, (a, b) in enumerate(zip(naive_ae, ols_ae)):
        for h in range(1, n_hz + 1):
            rows.append({"origin": i, "h": h, "actual": 40.0, "ae_naive_last": a * 1.5, "ae_seasonal_naive_52": a, "ae_calendar_ols": b})
    return pd.DataFrame(rows)


def test_thresholds_are_pinned():
    """Guards against quietly loosening the acceptance rule."""
    assert GATE_MIN_IMPROVEMENT == 0.05 and MIN_TRAIN == 130 and HORIZONS == (1, 2, 3, 4)


def test_gate_passes_on_clear_consistent_improvement():
    g = compute_gate(frame([10.0] * 30, [7.0] * 30), Y)
    assert g["passed"] and g["relative_mae_improvement"] == pytest.approx(0.30) and g["mean_abs_error_diff_ci95"][0] > 0


def test_gate_fails_when_no_improvement():
    assert not compute_gate(frame([10.0] * 30, [10.0] * 30), Y)["passed"]


def test_gate_fails_when_model_is_worse():
    assert not compute_gate(frame([10.0] * 30, [12.0] * 30), Y)["passed"]


def test_gate_fails_below_threshold_even_if_ci_positive():
    g = compute_gate(frame([10.0] * 30, [9.6] * 30), Y)  # 4% better, zero variance -> CI > 0
    assert g["mean_abs_error_diff_ci95"][0] > 0 and g["relative_mae_improvement"] < GATE_MIN_IMPROVEMENT
    assert not g["passed"]


def test_gate_fails_when_ci_includes_zero_despite_large_mean():
    naive = [10.0] * 20
    ols = [4.0, 14.0] * 10  # mean gain 1.0 (10%) but very noisy
    g = compute_gate(frame(naive, ols), Y)
    assert g["relative_mae_improvement"] >= GATE_MIN_IMPROVEMENT and g["mean_abs_error_diff_ci95"][0] <= 0
    assert not g["passed"]


def test_gate_uses_best_naive_baseline():
    e = frame([10.0] * 30, [9.0] * 30)
    e["ae_naive_last"] = 5.0  # naive-last is now the stronger baseline: model is worse than it
    g = compute_gate(e, Y)
    assert g["best_naive_baseline"] == "naive_last" and not g["passed"]


def _status(passed):
    gate = {"passed": passed, "mean_abs_error_diff_ci95": [0, 1]}
    err = pd.DataFrame([{"h": h, "actual": a, "calendar_ols": 38.0} for h in (1, 2, 3, 4) for a in (36.0, 40.0, 36.0, 40.0, 36.0, 40.0)])  # symmetric residuals +/-2 per horizon
    return Backtest(err, pd.DataFrame(), gate)


def test_forecast_is_suppressed_when_gate_fails():
    s = pd.Series(np.linspace(30, 50, 200), index=pd.date_range("2022-01-02", periods=200, freq="7D"))
    assert forecast_future(s, _status(False)) is None


def test_forecast_produced_only_when_gate_passes():
    s = pd.Series(np.linspace(30, 50, 200), index=pd.date_range("2022-01-02", periods=200, freq="7D"))
    fc = forecast_future(s, _status(True))
    assert len(fc) == 4 and (fc["lo80"] <= fc["forecast"]).all() and (fc["forecast"] <= fc["hi80"]).all()
    assert fc["target_week"].min() > s.index.max()  # strictly future


# ---- the real, recorded gate result must stay exactly as validated ----
STATUS = C.PROCESSED_DIR / "phase_a" / "forecast_status.json"


@pytest.mark.skipif(not STATUS.exists(), reason="run phase_a first")
def test_recorded_gate_result_unchanged_and_forecast_suppressed():
    st = json.loads(STATUS.read_text(encoding="utf-8"))["forecast"]
    g = st["gate"]
    assert g["passed"] is False and st["forecast_published"] is False
    assert g["relative_mae_improvement"] == pytest.approx(0.05329181198523184, abs=1e-9)
    assert g["mean_abs_error_diff_ci95"] == pytest.approx([-0.8914776674228622, 1.904120658381922], abs=1e-9)
    assert not (C.PROCESSED_DIR / "phase_a" / "forecast_national.parquet").exists()
