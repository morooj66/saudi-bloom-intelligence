"""National weekly forecast with a validation gate. Forecasts are exposed only if the gate passes.

Models (all fit on data available at the forecast origin; no future values used):
  * naive_last        - last observed week
  * seasonal_naive_52 - value 52 weeks before target week
  * calendar_ols      - direct h-step OLS on calendar covariates (known in advance) + trailing 4-week level
Evaluation is rolling-origin (expanding window), horizons 1-4 weeks. Gate: calendar_ols must beat the
best naive baseline by >=5% MAE with a bootstrap 95% CI (over origins) that excludes zero.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

HORIZONS = (1, 2, 3, 4)
MIN_TRAIN = 130
FEATURE_COLS = [
    "eid_al_fitr_in_week", "eid_al_adha_in_week", "valentines_day_in_week", "mothers_day_arab_in_week",
    "saudi_national_day_in_week", "saudi_founding_day_in_week", "new_years_eve_in_week", "ramadan_days_in_week",
    "annual_sin", "annual_cos",
]
GATE_MIN_IMPROVEMENT = 0.05


def _X(cal: pd.DataFrame, level: np.ndarray) -> np.ndarray:
    x = cal[FEATURE_COLS].astype(float).to_numpy()
    return np.column_stack([np.ones(len(x)), x, level])


def _ols_fit_predict(Xtr: np.ndarray, ytr: np.ndarray, Xte: np.ndarray, ridge: float = 1.0) -> np.ndarray:
    pen = ridge * np.eye(Xtr.shape[1]); pen[0, 0] = 0
    beta = np.linalg.solve(Xtr.T @ Xtr + pen, Xtr.T @ ytr)
    return Xte @ beta


def _level(y: np.ndarray) -> np.ndarray:
    """Trailing mean of the last 4 observed weeks at each index (uses only past + current)."""
    return pd.Series(y).rolling(4, min_periods=1).mean().to_numpy()


def predict_from_origin(y: np.ndarray, cal: pd.DataFrame, origin: int, h: int) -> dict:
    """Forecast position origin+h using only y[:origin+1]; cal must cover positions 0..origin+h."""
    lv = _level(y[: origin + 1])
    t_idx = np.arange(0, origin + 1 - h)  # training pairs: features at t+h, level at t, target y[t+h]
    Xtr = _X(cal.iloc[t_idx + h], lv[t_idx])
    ytr = y[t_idx + h]
    Xte = _X(cal.iloc[[origin + h]], lv[[origin]])
    ols = float(_ols_fit_predict(Xtr, ytr, Xte)[0])
    j = origin + h - 52
    sn = float(y[j]) if 0 <= j <= origin else np.nan
    return {"naive_last": float(y[origin]), "seasonal_naive_52": sn, "calendar_ols": max(0.0, ols)}


def compute_gate(e: pd.DataFrame, y: np.ndarray) -> dict:
    """Acceptance gate on a backtest-error frame. Pure function (unit-tested); thresholds are module constants."""
    # MASE scale: in-sample seasonal-naive MAE on first MIN_TRAIN weeks
    scale = float(np.nanmean(np.abs(y[52:MIN_TRAIN] - y[: MIN_TRAIN - 52])))
    # Gate
    best_naive = min(["naive_last", "seasonal_naive_52"], key=lambda m: e[f"ae_{m}"].mean())
    d = (e[f"ae_{best_naive}"] - e["ae_calendar_ols"]).groupby(e["origin"]).mean()  # >0 means OLS better
    rel = float(d.mean() / e.groupby("origin")[f"ae_{best_naive}"].mean().mean())
    rng = np.random.default_rng(0)
    boots = np.array([rng.choice(d.to_numpy(), len(d)).mean() for _ in range(2000)])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    passed = bool(rel >= GATE_MIN_IMPROVEMENT and lo > 0)
    return {"passed": passed, "best_naive_baseline": best_naive, "relative_mae_improvement": rel,
            "mean_abs_error_diff_ci95": [float(lo), float(hi)], "mase_scale": scale,
            "origins": int(e["origin"].nunique()), "horizons": list(HORIZONS),
            "mase_calendar_ols": float(e["ae_calendar_ols"].mean() / scale),
            "mase_best_naive": float(e[f"ae_{best_naive}"].mean() / scale),
            "rule": f"calendar_ols must beat best naive by >= {GATE_MIN_IMPROVEMENT:.0%} MAE and bootstrap 95% CI > 0",
            "caveat": "origins overlap (step=2 weeks, 4-week horizons) so the CI is optimistic; ~5 annual cycles only"}


@dataclass
class Backtest:
    errors: pd.DataFrame  # origin, h, week, actual, model columns, abs errors
    summary: pd.DataFrame
    gate: dict


def rolling_backtest(s: pd.Series, cal: pd.DataFrame, step: int = 2) -> Backtest:
    y = s.to_numpy(dtype=float)
    cal = cal.set_index("week_start").reindex(s.index).reset_index()  # history only; origin+h <= len(y)-1 always
    rows = []
    for origin in range(MIN_TRAIN, len(y) - max(HORIZONS), step):
        for h in HORIZONS:
            p = predict_from_origin(y, cal, origin, h)
            rows.append({"origin": origin, "origin_week": s.index[origin], "h": h, "target_week": s.index[origin + h],
                         "actual": y[origin + h], **p})
    e = pd.DataFrame(rows)
    models = ["naive_last", "seasonal_naive_52", "calendar_ols"]
    for m in models:
        e[f"ae_{m}"] = (e["actual"] - e[m]).abs()
    summ = e.groupby("h")[[f"ae_{m}" for m in models]].mean().rename(columns=lambda c: c[3:])
    overall = e[[f"ae_{m}" for m in models]].mean().rename(lambda c: c[3:]).to_frame("MAE_all").T
    summary = pd.concat([summ, overall.rename(index={"MAE_all": "all"})])
    gate = compute_gate(e, y)
    return Backtest(e, summary, gate)


def forecast_future(s: pd.Series, bt: Backtest, horizons=HORIZONS) -> pd.DataFrame | None:
    """Future forecasts from the last full week. Returns None unless the validation gate passed."""
    if not bt.gate["passed"]:
        return None
    from .calendar_features import build_weekly_calendar

    y = s.to_numpy(dtype=float)
    origin = len(y) - 1
    weeks = list(s.index) + [s.index[-1] + pd.Timedelta(weeks=k) for k in range(1, max(horizons) + 1)]
    cal = build_weekly_calendar(weeks)  # date-only features: valid for future weeks
    rows = []
    for h in horizons:
        p = predict_from_origin(y, cal, origin, h)  # reads y[:origin+1] only
        errs = bt.errors.loc[bt.errors["h"] == h]
        q = np.quantile((errs["actual"] - errs["calendar_ols"]).to_numpy(), [0.1, 0.9])
        rows.append({"target_week": weeks[origin + h], "h": h, "forecast": p["calendar_ols"],
                     "lo80": max(0.0, p["calendar_ols"] + q[0]), "hi80": p["calendar_ols"] + q[1],
                     "interval_basis": "empirical 10/90% quantiles of backtest residuals for this horizon"})
    return pd.DataFrame(rows)
