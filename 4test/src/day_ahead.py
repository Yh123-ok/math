"""只接收当天电价和历史预测；两次LP形成锁定的正常购电计划。"""
from functools import lru_cache
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix, csr_matrix, vstack
import config as cfg


def historical_price_value(history_prices, today_prices):
    """未来库存代理价只用过去28天；无历史时以已公布当日均价回退。"""
    if not len(history_prices): return float(np.mean(today_prices))
    rows=np.asarray(history_prices[-cfg.PRICE_HISTORY_DAYS:])
    age=np.arange(len(rows),0,-1)
    weight=2.**(-age/cfg.PRICE_HALF_LIFE)
    return float(np.average(rows.mean(axis=1),weights=weight))


@lru_cache(maxsize=1)
def matrices(n=144):
    size=5*n+2
    eq=lil_matrix((2*n,size))
    for t in range(n):
        eq[t,[t,n+t,2*n+t,3*n+t]]=[1,-1,1,-1]
        eq[n+t,[n+t,2*n+t,4*n+t,4*n+t+1]]=[-.9,1/.9,-1,1]
    ub=lil_matrix((1,size)); ub[0,5*n]=-1;ub[0,-1]=-1
    return eq.tocsr(),ub.tocsr()


def solve_plan(demand, prices, initial_soc, price_value, terminal_multiplier=cfg.EMERGENCY_MULTIPLIER):
    """demand已含安全余量。h是内部库存，按0.9转换后估计紧急代价。"""
    n=len(prices); eq,ub=matrices(n)
    rho=terminal_multiplier*cfg.ETA_DISCHARGE*price_value
    objective=np.r_[prices,np.zeros(4*n+1),rho]
    bounds=[(0,None)]*n+[(0,cfg.ENERGY_LIMIT)]*(2*n)+[(0,None)]*n
    bounds += [(cfg.SOC_MIN,cfg.SOC_MAX)]*(n+1)+[(0,None)]
    bounds[4*n]=(initial_soc,initial_soc)
    options={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9}
    first=linprog(objective,A_eq=eq,b_eq=np.r_[demand,np.zeros(n)],
        A_ub=ub,b_ub=[-cfg.SOC_TARGET],bounds=bounds,method='highs',options=options)
    if not first.success: raise RuntimeError('日前LP: '+first.message)
    tolerance=max(1e-6,1e-8*abs(first.fun))
    secondary=np.r_[np.zeros(n),np.ones(2*n),np.full(n,1e-8),np.zeros(n+2)]
    second=linprog(secondary,A_eq=eq,b_eq=np.r_[demand,np.zeros(n)],
        A_ub=vstack([ub,csr_matrix(objective[None,:])]),b_ub=[-cfg.SOC_TARGET,first.fun+tolerance],
        bounds=bounds,method='highs',options=options)
    if not second.success: raise RuntimeError('日前二阶段LP: '+second.message)
    x=second.x
    assert np.minimum(x[n:2*n],x[2*n:3*n]).max()<=cfg.PHYSICAL_TOL
    return {'q':x[:n].copy(),'reference_soc':x[4*n:5*n+1].copy(),
        'reference_charge':x[n:2*n].copy(),'reference_discharge':x[2*n:3*n].copy(),
        'reference_waste':x[3*n:4*n].copy(),'rho':rho,'price_value':price_value,
        'objective':float(first.fun),'cost_tolerance':tolerance,'status':second.message}
