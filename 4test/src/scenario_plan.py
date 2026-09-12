"""Causal two-stage day-ahead LP using full-day forecast errors from prior days.

Only q is committed. Scenario-specific variables are planning recourse, never
used as realized actions; the existing causal MPC executes the fixed q.
"""
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix
import config as cfg


def solve_scenario_plan(point, errors, prices, initial_soc, terminal_value):
    point=np.asarray(point,dtype=float)
    errors=np.asarray(errors,dtype=float)
    prices=np.asarray(prices,dtype=float)
    n=len(prices); m=len(errors)
    assert n==144 and errors.shape==(m,n) and 1<=m<=14
    # Shared q; per scenario c,u,w,e,S(145),h. The h variable is a soft
    # shortfall below 6000, priced as historically estimated replacement energy.
    block=5*n+2;size=n+m*block
    eq=lil_matrix((2*m*n,size));rhs=np.zeros(2*m*n)
    ub=lil_matrix((m,size));br=np.full(m,-cfg.SOC_TARGET)
    obj=np.zeros(size);obj[:n]=prices
    bounds=[(0,None)]*n
    for s in range(m):
        b=n+s*block
        c=np.arange(b,b+n);u=c+n;w=u+n;e=w+n
        S=np.arange(b+4*n,b+5*n+1);h=b+block-1
        bounds += [(0,cfg.ENERGY_LIMIT)]*(2*n)+[(0,None)]*(2*n)
        bounds += [(cfg.SOC_MIN,cfg.SOC_MAX)]*(n+1)+[(0,None)]
        bounds[S[0]]=(initial_soc,initial_soc)
        obj[e]=5*prices/m
        obj[h]=terminal_value/m
        ub[s,S[-1]]=-1;ub[s,h]=-1
        demand=point+errors[s]
        for t in range(n):
            r=s*n+t
            eq[r,[t,c[t],u[t],w[t],e[t]]]=[1,-1,1,-1,1]
            rhs[r]=demand[t]
            r2=m*n+r
            eq[r2,[c[t],u[t],S[t],S[t+1]]]=[-.9,1/.9,-1,1]
    result=linprog(obj,A_eq=eq.tocsr(),b_eq=rhs,A_ub=ub.tocsr(),b_ub=br,
                   bounds=bounds,method='highs')
    if not result.success:raise RuntimeError(result.message)
    return {'q':result.x[:n].copy(),'rho':terminal_value,'status':result.message,
            'objective':float(result.fun),'scenario_count':m}
