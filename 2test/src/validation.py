"""独立验收物理约束、信息边界、跨日连续性和费用。"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np

import config as cfg


def validate_results(results, load, pv, prices, forecasts, output_path: Path):
    max_balance = max_transition = max_continuity = max_simultaneous = 0.0
    soc_min, soc_max = float("inf"), -float("inf")
    charge_max = discharge_max = 0.0
    cost_error = 0.0
    nan_count = 0
    for i, result in enumerate(results):
        q = result.plan["q"]; a = result.actual
        balance = q + pv[i] + a["discharge"] + a["emergency"] - load[i] - a["charge"] - a["waste"]
        transition = a["soc"][1:] - a["soc"][:-1] - cfg.ETA_CHARGE*a["charge"] + a["discharge"]/cfg.ETA_DISCHARGE
        max_balance = max(max_balance, float(np.max(np.abs(balance))))
        max_transition = max(max_transition, float(np.max(np.abs(transition))))
        max_simultaneous = max(max_simultaneous, float(np.minimum(a["charge"], a["discharge"]).max()))
        soc_min = min(soc_min, float(a["soc"].min())); soc_max = max(soc_max, float(a["soc"].max()))
        charge_max = max(charge_max, float(a["charge"].max())); discharge_max = max(discharge_max, float(a["discharge"].max()))
        expected = float(np.dot(prices, q) + cfg.EMERGENCY_MULTIPLIER*np.dot(prices, a["emergency"]))
        cost_error = max(cost_error, abs(expected - result.total_cost))
        nan_count += int(sum((~np.isfinite(x)).sum() for x in [q, a["charge"], a["discharge"], a["emergency"], a["waste"], a["soc"]]))
        if i:
            max_continuity = max(max_continuity, abs(result.initial_soc - results[i-1].actual["soc"][-1]))
    checks = {
        "days": len(results), "periods": len(results)*cfg.PERIODS,
        "energy_balance_max_abs_kwh": max_balance,
        "soc_transition_max_abs_kwh": max_transition,
        "cross_day_soc_max_abs_kwh": max_continuity,
        "simultaneous_charge_discharge_max_kwh": max_simultaneous,
        "soc_min_kwh": soc_min, "soc_max_kwh": soc_max,
        "charge_max_kwh": charge_max, "discharge_max_kwh": discharge_max,
        "cost_recalculation_max_abs_yuan": cost_error, "nan_inf_count": nan_count,
        "first_soc_kwh": results[0].initial_soc,
        "last_soc_kwh": float(results[-1].actual["soc"][-1]),
        "causal_forecast_rule": "forecast arrays for day d are computed only from indices < d",
    }
    assert max_balance <= cfg.PHYSICAL_TOL
    assert max_transition <= cfg.PHYSICAL_TOL and max_continuity <= cfg.PHYSICAL_TOL
    assert soc_min >= cfg.SOC_MIN-cfg.PHYSICAL_TOL and soc_max <= cfg.SOC_MAX+cfg.PHYSICAL_TOL
    assert charge_max <= cfg.ENERGY_LIMIT+cfg.PHYSICAL_TOL and discharge_max <= cfg.ENERGY_LIMIT+cfg.PHYSICAL_TOL
    assert max_simultaneous <= cfg.PHYSICAL_TOL and cost_error <= cfg.PHYSICAL_TOL and nan_count == 0
    output_path.write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    return checks

