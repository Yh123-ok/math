"""严格因果的负载、光伏和净负荷预测。"""
from __future__ import annotations

import math
import numpy as np

import config as cfg


def _exp_weights(ages: np.ndarray, half_life: float) -> np.ndarray:
    w = np.power(2.0, -ages / half_life)
    return w / w.sum()


def _weighted_rows(values: np.ndarray, indices: np.ndarray, today: int, half_life: float) -> np.ndarray:
    ages = today - indices
    return np.average(values[indices], axis=0, weights=_exp_weights(ages, half_life))


def _grid_weight(actual, pred_a, pred_b, valid_days, daytime_only=False) -> float:
    if len(valid_days) < cfg.ENSEMBLE_MIN_DAYS:
        return 0.5
    best = (float("inf"), 0.5)
    for weight in np.linspace(0, 1, 11):
        pred = weight * pred_a[valid_days] + (1 - weight) * pred_b[valid_days]
        if daytime_only:
            mask = (pred_a[valid_days] + pred_b[valid_days]) > 1e-9
            loss = np.abs(actual[valid_days] - pred)[mask].sum() / max(actual[valid_days][mask].sum(), 1.0)
        else:
            loss = np.mean(np.abs(actual[valid_days] - pred))
        candidate = (float(loss), float(weight))
        if candidate < best:
            best = candidate
    return best[1]


def _pv_weight_grid(actual, candidates, valid_days):
    if len(valid_days) < cfg.ENSEMBLE_MIN_DAYS:
        return (0.5, 0.5, 0.0)
    best = (float("inf"), (0.5, 0.5, 0.0))
    for ia in range(11):
        for ib in range(11 - ia):
            ic = 10 - ia - ib
            weights = (ia / 10, ib / 10, ic / 10)
            pred = sum(w * candidates[k][valid_days] for k, w in enumerate(weights))
            mask = sum(candidates[k][valid_days] for k in range(3)) > 1e-9
            loss = np.abs(actual[valid_days] - pred)[mask].sum() / max(actual[valid_days][mask].sum(), 1.0)
            candidate = (float(loss), weights)
            if candidate < best:
                best = candidate
    return best[1]


def generate_causal_forecasts(dates, load, pv):
    """返回所有候选预测及每天当时可得的组合权重。"""
    days, periods = load.shape
    nan = np.full((days, periods), np.nan)
    load_a, load_b0, load_b, load_final = nan.copy(), nan.copy(), nan.copy(), nan.copy()
    pv_a, pv_b, pv_c, pv_final = nan.copy(), nan.copy(), nan.copy(), nan.copy()
    load_weight = np.full(days, np.nan)
    pv_weights = np.full((days, 3), np.nan)

    for d in range(days):
        if d == 0:
            # 无历史的第一天没有虚构预测。计划阶段由冷启动规则处理。
            continue
        load_a[d] = load[d - 1]
        pv_a[d] = pv[d - 1]

        start = max(0, d - cfg.LOAD_HISTORY_DAYS)
        history = np.arange(start, d)
        exact = history[[dates[j].weekday() == dates[d].weekday() for j in history]]
        broad = history[[((dates[j].weekday() < 5) == (dates[d].weekday() < 5)) for j in history]]
        broad_pred = _weighted_rows(load, broad if len(broad) else history, d, cfg.LOAD_DATE_HALF_LIFE)
        exact_pred = _weighted_rows(load, exact, d, cfg.LOAD_DATE_HALF_LIFE) if len(exact) else broad_pred
        shrink = len(exact) / (len(exact) + cfg.LOAD_SHRINK_K)
        load_b0[d] = shrink * exact_pred + (1 - shrink) * broad_pred
        ratios = []
        for j in range(max(1, d - cfg.LOAD_LEVEL_DAYS), d):
            if np.isfinite(load_b0[j]).all() and load_b0[j].sum() > 0:
                ratios.append(load[j].sum() / load_b0[j].sum())
        level = float(np.clip(np.median(ratios), 0.8, 1.2)) if ratios else 1.0
        load_b[d] = level * load_b0[d]

        m = min(cfg.PV_EWMA_DAYS, d)
        indices = np.arange(d - m, d)
        ages = d - indices
        w = _exp_weights(ages - 1, cfg.PV_EWMA_HALF_LIFE)
        pv_b[d] = np.average(pv[indices], axis=0, weights=w)

        valid_energy = np.maximum(pv[indices].sum(axis=1), 1e-12)
        shapes = pv[indices] / valid_energy[:, None]
        shape = np.average(shapes, axis=0, weights=w)
        shape_sum = shape.sum()
        shape = shape / shape_sum if shape_sum > 0 else shape
        recent_indices = np.arange(max(0, d - 3), d)[::-1]
        recent_weights = np.array(cfg.PV_RECENT_WEIGHTS[:len(recent_indices)], dtype=float)
        recent_weights /= recent_weights.sum()
        recent_total = float(np.dot(recent_weights, pv[recent_indices].sum(axis=1)))
        trend_indices = np.arange(max(0, d - cfg.PV_TREND_DAYS), d)
        if len(trend_indices) >= 3:
            tw = _exp_weights(d - trend_indices, cfg.PV_TREND_DAYS / 2)
            x = trend_indices.astype(float)
            xbar, y = np.dot(tw, x), pv[trend_indices].sum(axis=1)
            ybar = np.dot(tw, y)
            denom = np.dot(tw, (x - xbar) ** 2)
            slope = np.dot(tw, (x - xbar) * (y - ybar)) / denom if denom > 0 else 0.0
            trend_total = max(0.0, ybar + slope * (d - xbar))
        else:
            trend_total = recent_total
        total = cfg.PV_TOTAL_BLEND * recent_total + (1 - cfg.PV_TOTAL_BLEND) * trend_total
        pv_c[d] = np.maximum(0.0, total * shape)

        valid = np.arange(max(1, d - cfg.ENSEMBLE_VALIDATION_DAYS), d)
        valid_load = valid[np.isfinite(load_a[valid]).all(axis=1) & np.isfinite(load_b[valid]).all(axis=1)]
        a = _grid_weight(load, load_a, load_b, valid_load)
        load_weight[d] = a
        load_final[d] = a * load_a[d] + (1 - a) * load_b[d]

        valid_pv = valid[np.isfinite(pv_a[valid]).all(axis=1) & np.isfinite(pv_b[valid]).all(axis=1)
                         & np.isfinite(pv_c[valid]).all(axis=1)]
        bw = _pv_weight_grid(pv, (pv_a, pv_b, pv_c), valid_pv)
        pv_weights[d] = bw
        pv_final[d] = bw[0] * pv_a[d] + bw[1] * pv_b[d] + bw[2] * pv_c[d]

    return {
        "load_a": load_a, "load_b": load_b, "load_final": load_final,
        "pv_a": pv_a, "pv_b": pv_b, "pv_c": pv_c, "pv_final": pv_final,
        "load_weight_a": load_weight, "pv_weights": pv_weights,
        "net_error": (load - pv) - (load_final - pv_final),
    }


def weighted_safety_margin(day: int, net_error: np.ndarray, alpha: float) -> np.ndarray:
    """只使用 day 之前误差，按日期和相邻时段加权求正分位数。"""
    periods = net_error.shape[1]
    result = np.zeros(periods)
    first = max(1, day - cfg.ERROR_HISTORY_DAYS)
    historical_days = np.arange(first, day)
    if not len(historical_days):
        return result
    for t in range(periods):
        slots = np.arange(max(0, t - cfg.ERROR_SLOT_RADIUS), min(periods, t + cfg.ERROR_SLOT_RADIUS + 1))
        values, weights = [], []
        for j in historical_days:
            if not np.isfinite(net_error[j, slots]).all():
                continue
            for s in slots:
                values.append(net_error[j, s])
                weights.append(2 ** (-(day - j) / cfg.ERROR_DATE_HALF_LIFE)
                               * math.exp(-abs(s - t) / cfg.ERROR_SLOT_SCALE))
        if len(values) < cfg.ERROR_MIN_SAMPLES:
            continue
        values_array = np.asarray(values, dtype=float)
        weights_array = np.asarray(weights, dtype=float)
        order = np.argsort(values_array)
        sorted_values, sorted_weights = values_array[order], weights_array[order]
        cumulative = np.cumsum(sorted_weights) / sorted_weights.sum()
        result[t] = max(0.0, float(sorted_values[np.searchsorted(cumulative, alpha, side="left")]))
    return result
