"""方案回放、滚动参数选择和全年主策略执行。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import numpy as np

import config as cfg
from .forecasting import weighted_safety_margin
from .optimization import day_ahead_plan, execute_one_step, realized_cost


@dataclass
class DayResult:
    day: int
    scheme: int
    alpha: float
    kappa: float
    initial_soc: float
    plan: dict
    actual: dict
    planned_cost: float
    emergency_cost: float
    total_cost: float


def _forecast_for_scheme(day, scheme, forecasts):
    if scheme == 0:
        return forecasts["load_a"][day], forecasts["pv_a"][day]
    if scheme == 1:
        return forecasts["load_b"][day], forecasts["pv_b"][day]
    return forecasts["load_final"][day], forecasts["pv_final"][day]


def simulate_day(day, scheme, alpha, kappa, initial_soc, load, pv, prices, forecasts, lexicographic=True):
    if day == 0:
        q = np.zeros(cfg.PERIODS)
        plan = {"q": q, "reference_charge": np.zeros(cfg.PERIODS),
                "reference_discharge": np.zeros(cfg.PERIODS), "reference_waste": np.zeros(cfg.PERIODS),
                "reference_soc": np.full(cfg.PERIODS+1, initial_soc), "primary_optimum": 0.0,
                "primary_realized": 0.0, "rho": 0.0, "epsilon": 0.0}
    else:
        load_hat, pv_hat = _forecast_for_scheme(day, scheme, forecasts)
        if not np.isfinite(load_hat).all() or not np.isfinite(pv_hat).all():
            raise ValueError(f"第{day}天预测不可用")
        margin = weighted_safety_margin(day, forecasts["net_error"], alpha) if scheme == 2 else np.zeros(cfg.PERIODS)
        plan = day_ahead_plan(load_hat - pv_hat, margin, prices, initial_soc, kappa, lexicographic=lexicographic)
    actual = execute_one_step(load[day] - pv[day], plan["q"], prices, initial_soc)
    planned, urgent, total = realized_cost(plan["q"], actual["emergency"], prices)
    return DayResult(day, scheme, alpha, kappa, initial_soc, plan, actual, planned, urgent, total)


def replay(start_day, end_day, initial_soc, scheme, alpha, kappa, load, pv, prices, forecasts,
           lexicographic=False):
    results, soc = [], float(initial_soc)
    for day in range(start_day, end_day):
        result = simulate_day(day, scheme, alpha, kappa, soc, load, pv, prices, forecasts,
                              lexicographic=lexicographic)
        results.append(result)
        soc = float(result.actual["soc"][-1])
    raw_cost = sum(r.total_cost for r in results)
    terminal_value = cfg.TERMINAL_VALUE_FACTOR * float(np.mean(prices)) * (soc - initial_soc)
    return results, raw_cost - terminal_value


def _local_grid(alpha, kappa):
    alphas = sorted({round(float(np.clip(alpha + i*cfg.ALPHA_LOCAL_STEP, 0.5, 0.99)), 2) for i in range(-1, 2)})
    kappas = sorted({round(max(0.0, kappa + i*cfg.KAPPA_LOCAL_STEP), 3) for i in range(-1, 2)})
    return alphas, kappas


def select_month_parameters(month_day, month_number, common_initial_soc, previous, load, pv, prices, forecasts):
    """在月初用此前最多60天进行完整因果回放，选择当月方案和参数。"""
    start = max(cfg.CALIBRATION_START_DAY_INDEX, month_day - cfg.CALIBRATION_WINDOW_DAYS)
    if month_day < cfg.COLD_START_HISTORY_DAYS:
        return {"scheme": cfg.COLD_START_SCHEME, "alpha": cfg.COLD_START_ALPHA,
                "kappa": cfg.COLD_START_KAPPA, "validation_cost": float("nan"),
                "best_cost": float("nan"), "validation_start": start,
                "validation_end": month_day, "candidates": 0,
                "selection_stage": "cold_start_guard"}
    if month_day <= start:
        return {"scheme": 2, "alpha": 0.8, "kappa": 1.0, "validation_cost": float("nan"),
                "validation_start": start, "validation_end": month_day, "candidates": 0}
    from concurrent.futures import ThreadPoolExecutor
    specs = [(0, 0.5, 1.0, "baseline"), (1, 0.5, 1.0, "baseline")]
    if month_number in cfg.FULL_SEARCH_MONTHS or previous is None:
        specs += [(2, a, k, "coarse") for a in cfg.ALPHA_COARSE for k in cfg.KAPPA_COARSE]
    else:
        center_a = previous.get("alpha", 0.8) if previous.get("scheme", 2) == 2 else 0.8
        center_k = previous.get("kappa", 1.0) if previous.get("scheme", 2) == 2 else 1.0
        local_a, local_k = _local_grid(center_a, center_k)
        specs += [(2, a, k, "monthly_local") for a in local_a for k in local_k]

    def evaluate(spec):
        scheme, alpha, kappa, stage = spec
        _, score = replay(start, month_day, common_initial_soc, scheme, alpha, kappa,
                          load, pv, prices, forecasts, lexicographic=False)
        return (score, scheme, alpha, kappa, stage)
    with ThreadPoolExecutor(max_workers=cfg.CALIBRATION_WORKERS) as pool:
        candidates = list(pool.map(evaluate, specs))
    if month_number in cfg.FULL_SEARCH_MONTHS or previous is None:
        coarse_best = min((x for x in candidates if x[1] == 2), key=lambda x: (x[0], x[2], x[3]))
        local_a, local_k = _local_grid(coarse_best[2], coarse_best[3])
        tested = {(x[1], x[2], x[3]) for x in candidates}
        extra_specs = [(2, a, k, "local") for a in local_a for k in local_k if (2,a,k) not in tested]
        with ThreadPoolExecutor(max_workers=cfg.CALIBRATION_WORKERS) as pool:
            candidates += list(pool.map(evaluate, extra_specs))
    candidates.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
    best = candidates[0]
    # 费用差不超过0.1%时选更简单的方案。
    eligible = [x for x in candidates if x[0] <= best[0] * 1.001]
    chosen = min(eligible, key=lambda x: (x[1], x[0]))
    return {"scheme": chosen[1], "alpha": chosen[2], "kappa": chosen[3],
            "validation_cost": chosen[0], "best_cost": best[0],
            "validation_start": start, "validation_end": month_day,
            "candidates": len(candidates), "all_candidates": candidates}


def run_year(dates, load, pv, prices, forecasts, progress=None):
    results = []
    selections = []
    soc = cfg.SOC_INITIAL
    day_start_socs = []
    current = {"scheme": cfg.COLD_START_SCHEME, "alpha": cfg.COLD_START_ALPHA,
               "kappa": cfg.COLD_START_KAPPA}
    for day, current_date in enumerate(dates):
        day_start_socs.append(soc)
        if day >= 31 and current_date.day == 1:
            validation_start = max(cfg.CALIBRATION_START_DAY_INDEX, day - cfg.CALIBRATION_WINDOW_DAYS)
            common_soc = day_start_socs[validation_start]
            selected = select_month_parameters(day, current_date.month, common_soc, current,
                                               load, pv, prices, forecasts)
            selected["effective_date"] = current_date.isoformat()
            selections.append(selected)
            current = selected
            if progress:
                progress(f"参数更新 {current_date}: 方案{current['scheme']}, alpha={current['alpha']}, kappa={current['kappa']}")
        result = simulate_day(day, current["scheme"], current["alpha"], current["kappa"],
                              soc, load, pv, prices, forecasts)
        results.append(result)
        soc = float(result.actual["soc"][-1])
    return results, selections
