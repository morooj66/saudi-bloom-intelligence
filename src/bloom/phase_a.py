"""Phase A orchestration: seasonal analysis, regional comparison tables, gated forecast. Writes data/processed/phase_a/.

Run:  PYTHONPATH=src .venv/bin/python -m bloom.phase_a
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

from . import config as C
from .forecast import GATE_MIN_IMPROVEMENT, HORIZONS, MIN_TRAIN
from .integrity import PROV, verify
from .pipeline import sha256_path, write_provenance
from .analysis import event_lift, event_lift_summary, month_profile, national_series, regional_rank_table, regional_share_table, stl_strength
from .forecast import forecast_future, rolling_backtest

# (group stem, term, role). Forecast target = commercial flower-shop term from the commercial-only comparison.
TARGETS = [("groupB", "محل ورد", "primary_commercial"), ("groupB", "بوكيه ورد", "secondary_commercial"),
           ("groupB", "توصيل ورد", "secondary_commercial"), ("groupA", "ورد", "general_context")]
FORECAST_TARGET = ("groupB", "محل ورد")


def run(root: Path = C.ROOT) -> dict:
    P = C.paths(root)
    OUT, PROC = P.phase_a, P.processed
    pre = verify(P.root, stage="processed")  # fail closed: never analyse unverified inputs
    if not pre.ok:
        raise RuntimeError("Input integrity check failed: " + "; ".join(f"{c['name']} ({c['detail']})" for c in pre.failures))
    OUT.mkdir(parents=True, exist_ok=True)

    def _w(df: pd.DataFrame, name: str) -> None:
        df.to_parquet(OUT / f"{name}.parquet", index=False)
        df.to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8-sig")

    cal = pd.read_parquet(PROC / "calendar_weekly.parquet")
    months, lifts, summ, strengths = [], [], [], []
    bt_by_target = {}
    for stem, term, role in TARGETS:
        analytic = pd.read_parquet(PROC / f"timeline_{stem}_analytic_weekly.parquet")
        scale_id = analytic["scale_id"].iloc[0]
        s = national_series(analytic, term)
        m = month_profile(s).assign(term=term, comparison_group=analytic["comparison_group"].iloc[0], scale_id=scale_id, role=role)
        months.append(m)
        l = event_lift(s, cal)
        lifts.append(l.assign(term=term, scale_id=scale_id))
        summ.append(event_lift_summary(l).assign(term=term, scale_id=scale_id))
        strengths.append({"term": term, "scale_id": scale_id, "role": role, **stl_strength(s)})
        bt_by_target[(stem, term)] = (s, rolling_backtest(s, cal))
    _w(pd.concat(months), "month_profile")
    _w(pd.concat(lifts), "event_lift")
    _w(pd.concat(summ), "event_lift_summary")
    _w(pd.DataFrame(strengths), "stl_strength")

    # backtests for every target; forecast exposed only for the designated target and only if gate passed
    gates, bt_sum, bt_err = {}, [], []
    for (stem, term), (s, bt) in bt_by_target.items():
        gates[f"{stem}|{term}"] = bt.gate
        bt_sum.append(bt.summary.reset_index(names="h").astype({"h": str}).assign(term=term, stem=stem))
        bt_err.append(bt.errors.assign(term=term, stem=stem))
    _w(pd.concat(bt_sum), "backtest_summary")
    _w(pd.concat(bt_err), "backtest_errors")
    s, bt = bt_by_target[FORECAST_TARGET]
    fc = forecast_future(s, bt)
    forecast_status = {"target": list(FORECAST_TARGET), "gate": bt.gate, "forecast_published": fc is not None}
    if fc is not None:
        _w(fc, "forecast_national")
    elif (OUT / "forecast_national.parquet").exists():
        raise RuntimeError("Stale forecast file present while gate failed; remove it manually (phase_a never deletes outputs).")

    # regional (13 regions): relative comparisons; scale metadata preserved per row
    single = pd.read_parquet(PROC / "region_single_term_index.parquet")
    share = pd.read_parquet(PROC / "region_groupA_share.parquet")
    _w(regional_rank_table(single), "regional_index_by_term")
    _w(regional_share_table(share), "regional_share_groupA")
    (OUT / "forecast_status.json").write_text(json.dumps({"forecast": forecast_status, "all_gates": gates}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    from .ingest import fingerprint

    man = json.loads(P.manifest_json.read_text(encoding="utf-8"))
    write_provenance(OUT, fingerprint(man), {
        "processed_provenance_sha256": sha256_path(PROC / PROV),
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "gate_constants": {"min_improvement": GATE_MIN_IMPROVEMENT, "min_train": MIN_TRAIN, "horizons": list(HORIZONS)},
    })
    return forecast_status


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[argv.index("--root") + 1]) if argv and "--root" in argv else C.ROOT
    try:
        r = run(root)
    except Exception as exc:
        print(f"PHASE A FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"target": r["target"], "forecast_published": r["forecast_published"],
                      "gate_passed": r["gate"]["passed"], "rel_improvement": round(r["gate"]["relative_mae_improvement"], 4),
                      "ci95": r["gate"]["mean_abs_error_diff_ci95"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
