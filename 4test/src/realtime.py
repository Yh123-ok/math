"""当前实际值只能以一个标量传入；未来需求仅来自0:00冻结的预测。"""
from functools import lru_cache
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix
import config as cfg


@lru_cache(maxsize=144)
def horizon_matrix(n):
    # c[n], u[n], S[n+1], h[1]；紧急量等于正缺口减放电，可从变量中消去。
    eq=lil_matrix((n,3*n+2))
    for t in range(n):
        eq[t,[t,n+t,2*n+t,2*n+t+1]]=[-.9,1/.9,-1,1]
    ub=lil_matrix((1,3*n+2));ub[0,3*n]=-1;ub[0,-1]=-1
    return eq.tocsr(),ub.tocsr()


def decide_step(t, actual_net_now, q, forecast_demand, prices, soc, rho, mode):
    """两种控制器均不改q，且不允许紧急购电充电或同段充放电。"""
    gap=float(actual_net_now-q[t])
    charge=discharge=emergency=waste=0.
    if gap<=0:
        charge=min(-gap,cfg.ENERGY_LIMIT,max(0.,(cfg.SOC_MAX-soc)/.9))
        waste=-gap-charge
    else:
        available=min(gap,cfg.ENERGY_LIMIT,.9*max(0.,soc-cfg.SOC_MIN))
        if mode=='greedy' or available<=1e-9:
            discharge=available
        elif mode=='mpc':
            # 本段真实缺口替换预测；prices的后续段已于当天0:00公布。
            gaps=np.asarray(forecast_demand[t:]-q[t:]).copy();gaps[0]=gap
            n=len(gaps);eq,ub=horizon_matrix(n)
            surplus=np.minimum(np.maximum(-gaps,0),cfg.ENERGY_LIMIT)
            deficits=np.minimum(np.maximum(gaps,0),cfg.ENERGY_LIMIT)
            objective=np.r_[np.zeros(n),-5.*prices[t:],np.zeros(n+1),rho]
            bounds=[(0,float(x)) for x in surplus]+[(0,float(x)) for x in deficits]
            bounds += [(cfg.SOC_MIN,cfg.SOC_MAX)]*(n+1)+[(0,None)]
            bounds[2*n]=(soc,soc)
            result=linprog(objective,A_eq=eq,b_eq=np.zeros(n),A_ub=ub,
                b_ub=[-cfg.SOC_TARGET],bounds=bounds,method='highs',
                options={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9})
            if not result.success: raise RuntimeError(f'MPC时段{t}: '+result.message)
            discharge=float(np.clip(result.x[n],0,available))
        else: raise ValueError(mode)
        emergency=max(0.,gap-discharge)
    end=soc+.9*charge-discharge/.9
    return charge,discharge,emergency,waste,end


def execute_day(actual_net, plan, forecast_demand, prices, initial_soc, mode):
    q=plan['q'];original=q.copy()
    values={k:np.zeros(144) for k in ('charge','discharge','emergency','waste')}
    values['soc']=np.zeros(145);values['soc'][0]=initial_soc
    for t in range(144):
        c,u,e,w,end=decide_step(t,float(actual_net[t]),q,forecast_demand,prices,
                             values['soc'][t],plan['rho'],mode)
        for key,value in zip(('charge','discharge','emergency','waste'),(c,u,e,w)):
            values[key][t]=value
        values['soc'][t+1]=end
    assert np.array_equal(original,q), '日内修改了正常购电计划'
    return values
