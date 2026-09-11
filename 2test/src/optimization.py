"""日前购电线性规划和逐时段因果执行。"""
from __future__ import annotations

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix, csr_matrix, vstack

import config as cfg


def day_ahead_plan(net_forecast, margin, prices, initial_soc, kappa, lexicographic=True):
    """在预测净负荷与安全余量下，确定全天144段正常购电量。

    返回 q,c,d,w,s。q 是正式计划，其余是预测条件下的储能参考轨迹。
    """
    n = len(prices)
    # q,c,d,w 各n个，S有n+1个，h一个。
    size = 4 * n + n + 2
    q = np.arange(0, n); c = np.arange(n, 2*n); discharge = np.arange(2*n, 3*n)
    w = np.arange(3*n, 4*n); soc = np.arange(4*n, 5*n+1); h = size - 1
    aeq = lil_matrix((2*n, size)); beq = np.zeros(2*n)
    demand = np.asarray(net_forecast) + np.asarray(margin)
    for t in range(n):
        aeq[t, [q[t], c[t], discharge[t], w[t]]] = [1, -1, 1, -1]
        beq[t] = demand[t]
        aeq[n+t, [c[t], discharge[t], soc[t], soc[t+1]]] = [
            -cfg.ETA_CHARGE, 1/cfg.ETA_DISCHARGE, -1, 1]
    aub = lil_matrix((1, size)); aub[0, soc[-1]] = -1; aub[0, h] = -1
    bub = np.array([-cfg.SOC_TARGET])
    bounds = [(0, None)]*n + [(0, cfg.ENERGY_LIMIT)]*(2*n) + [(0, None)]*n \
             + [(cfg.SOC_MIN, cfg.SOC_MAX)]*(n+1) + [(0, None)]
    bounds[4*n] = (initial_soc, initial_soc)
    primary = np.zeros(size); primary[q] = prices
    rho = kappa * cfg.ETA_DISCHARGE * float(np.mean(prices))
    primary[h] = rho
    options = {"primal_feasibility_tolerance": 1e-9, "dual_feasibility_tolerance": 1e-9}
    first = linprog(primary, A_ub=aub.tocsr(), b_ub=bub, A_eq=aeq.tocsr(), b_eq=beq,
                    bounds=bounds, method="highs", options=options)
    if not first.success:
        raise RuntimeError(f"日前LP失败: {first.message}")
    eps = max(1e-6, cfg.LP_TOL * abs(first.fun))
    if not lexicographic:
        x = first.x
        return {
            "q": x[q], "reference_charge": x[c], "reference_discharge": x[discharge],
            "reference_waste": x[w], "reference_soc": x[soc],
            "primary_optimum": float(first.fun), "primary_realized": float(primary @ x),
            "rho": rho, "epsilon": eps,
        }
    secondary = np.zeros(size); secondary[c] = 1; secondary[discharge] = 1
    secondary[w] = cfg.THROUGHPUT_EPS
    second_aub = vstack([aub.tocsr(), csr_matrix(primary.reshape(1, -1))])
    second_bub = np.r_[bub, first.fun + eps]
    second = linprog(secondary, A_ub=second_aub, b_ub=second_bub,
                     A_eq=aeq.tocsr(), b_eq=beq, bounds=bounds,
                     method="highs", options=options)
    if not second.success:
        raise RuntimeError(f"日前二阶段LP失败: {second.message}")
    x = second.x
    return {
        "q": x[q], "reference_charge": x[c], "reference_discharge": x[discharge],
        "reference_waste": x[w], "reference_soc": x[soc],
        "primary_optimum": float(first.fun), "primary_realized": float(primary @ x),
        "rho": rho, "epsilon": eps,
    }


def execute_one_step(actual_net, plan_q, prices, initial_soc):
    """每十分钟求解当前时段的紧急购电最小问题。

    已计划购电费是沉没成本。当前目标等价于最小化5*p_t*e_t，并以极小
    次级代价排除充放电循环。闭式实现与该单时段LP完全等价，运行快且可审计。
    """
    n = len(prices)
    charge = np.zeros(n); discharge = np.zeros(n); emergency = np.zeros(n); waste = np.zeros(n)
    soc = np.zeros(n+1); soc[0] = initial_soc
    for t in range(n):
        gap = float(actual_net[t] - plan_q[t])
        if gap > 0:
            discharge[t] = min(gap, cfg.ENERGY_LIMIT,
                               cfg.ETA_DISCHARGE * max(0.0, soc[t] - cfg.SOC_MIN))
            emergency[t] = gap - discharge[t]
        else:
            surplus = -gap
            charge[t] = min(surplus, cfg.ENERGY_LIMIT,
                            max(0.0, (cfg.SOC_MAX - soc[t]) / cfg.ETA_CHARGE))
            waste[t] = surplus - charge[t]
        soc[t+1] = soc[t] + cfg.ETA_CHARGE*charge[t] - discharge[t]/cfg.ETA_DISCHARGE
    return {"charge": charge, "discharge": discharge, "emergency": emergency,
            "waste": waste, "soc": soc}


def realized_cost(plan_q, emergency, prices):
    planned = float(np.dot(prices, plan_q))
    urgent = float(cfg.EMERGENCY_MULTIPLIER * np.dot(prices, emergency))
    return planned, urgent, planned + urgent
