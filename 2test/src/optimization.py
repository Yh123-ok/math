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
    # kappa只缩放历史误差分位数安全余量，不与日末SOC惩罚混用。
    demand = np.asarray(net_forecast) + float(kappa) * np.asarray(margin)
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
    # 日末SOC不足可能在下一时段触发紧急购电，按五倍末时段电价计价。
    rho = cfg.EMERGENCY_MULTIPLIER * float(prices[-1])
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


def execute_one_step(actual_net, plan_q, prices, initial_soc,
                     reference_soc=None, reference_discharge=None):
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
            available = min(cfg.ENERGY_LIMIT,
                            cfg.ETA_DISCHARGE * max(0.0, soc[t] - cfg.SOC_MIN))
            allowed = available
            if reference_soc is not None and reference_discharge is not None:
                planned_allowance = max(float(reference_discharge[t]),
                                        cfg.ETA_DISCHARGE*max(0.0,soc[t]-float(reference_soc[t+1])))
                # 非最高价时不提前透支计划SOC；到剩余时域峰价则释放全部可用电量。
                if prices[t] < 0.98*float(np.max(prices[t:])):
                    allowed = min(available, planned_allowance)
            discharge[t] = min(gap, allowed)
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


def stochastic_day_ahead_plan(net_forecast, error_scenarios, scenario_weights,
                              prices, initial_soc):
    """两阶段随机LP：q为场景共用日前决策，其余变量按历史误差场景追溯。"""
    net_forecast = np.asarray(net_forecast, dtype=float)
    errors = np.asarray(error_scenarios, dtype=float)
    weights = np.asarray(scenario_weights, dtype=float)
    weights = weights / weights.sum()
    ns, n = errors.shape
    block = 5*n + 1  # c,d,w,e,S(n+1)
    size = n + ns*block
    rows = 2*ns*n
    aeq = lil_matrix((rows, size)); beq = np.zeros(rows)
    objective = np.zeros(size); objective[:n] = prices
    bounds = [(0, None)]*n
    soc_indices = []
    for s in range(ns):
        base = n + s*block
        c = np.arange(base, base+n); d = np.arange(base+n, base+2*n)
        w = np.arange(base+2*n, base+3*n); e = np.arange(base+3*n, base+4*n)
        soc = np.arange(base+4*n, base+5*n+1); soc_indices.append(soc)
        objective[c] = cfg.STOCHASTIC_THROUGHPUT_PENALTY*weights[s]
        objective[d] = cfg.STOCHASTIC_THROUGHPUT_PENALTY*weights[s]
        objective[e] = cfg.STOCHASTIC_PLANNING_EMERGENCY_MULTIPLIER*weights[s]*prices
        bounds += [(0,cfg.ENERGY_LIMIT)]*n + [(0,cfg.ENERGY_LIMIT)]*n
        bounds += [(0,None)]*n + [(0,None)]*n
        bounds += [(cfg.SOC_MIN,cfg.SOC_MAX)]*(n+1)
        bounds[n + s*block + 4*n] = (initial_soc, initial_soc)
        bounds[n + s*block + 5*n] = (cfg.SOC_TARGET, cfg.SOC_MAX)
        for t in range(n):
            r = s*n+t
            aeq[r, [t,c[t],d[t],w[t],e[t]]] = [1,-1,1,-1,1]
            beq[r] = net_forecast[t] + errors[s,t]
            r2 = ns*n+s*n+t
            aeq[r2, [c[t],d[t],soc[t],soc[t+1]]] = [
                -cfg.ETA_CHARGE,1/cfg.ETA_DISCHARGE,-1,1]
    options = {"primal_feasibility_tolerance":1e-8,"dual_feasibility_tolerance":1e-8}
    solved = linprog(objective, A_eq=aeq.tocsr(), b_eq=beq, bounds=bounds,
                     method="highs", options=options)
    if not solved.success:
        raise RuntimeError(f"随机日前LP失败: {solved.message}")
    x=solved.x
    def average(offset):
        return sum(weights[s]*x[n+s*block+offset:n+s*block+offset+n] for s in range(ns))
    ref_soc = sum(weights[s]*x[soc_indices[s]] for s in range(ns))
    return {"q":x[:n], "reference_charge":average(0),
            "reference_discharge":average(n), "reference_waste":average(2*n),
            "reference_soc":ref_soc, "primary_optimum":float(solved.fun),
            "primary_realized":float(solved.fun), "rho":0.0, "epsilon":0.0}
