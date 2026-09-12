"""物理验收与真正扰动输入的因果性测试。"""
import numpy as np
import config as cfg
from .forecasting import generate_causal_forecasts, weighted_safety_margin
from .day_ahead import solve_plan, historical_price_value
from .realtime import execute_day, decide_step
from .backtest import choose_from_history


def validate_physics(data, streams):
    checks={}
    for name,days in streams.items():
        q=np.array([r['plan']['q'] for r in days])
        a={k:np.array([r['actual'][k] for r in days]) for k in ('charge','discharge','emergency','waste','soc')}
        c,u,e,w,s=(a[k] for k in ('charge','discharge','emergency','waste','soc'))
        checks[name]={
            'balance_max_kwh':float(np.max(np.abs(q+data.pv+u+e-data.load-c-w))),
            'state_equation_max_kwh':float(np.max(np.abs(np.diff(s,axis=1)-.9*c+u/.9))),
            'soc_min_kwh':float(s.min()),'soc_max_kwh':float(s.max()),
            'charge_max_kwh':float(c.max()),'discharge_max_kwh':float(u.max()),
            'simultaneous_max_kwh':float(np.minimum(c,u).max()),
            'cross_day_soc_max_kwh':float(np.max(np.abs(s[1:,0]-s[:-1,-1]))),
            'first_soc_error_kwh':float(abs(s[0,0]-6000)),
            'emergency_while_charging_max_kwh':float(np.minimum(e,c).max()),
            'negative_min_kwh':float(min(x.min() for x in (q,c,u,e,w))),
            'nonfinite_count':int(sum(np.sum(~np.isfinite(x)) for x in (q,c,u,e,w,s))),
            'four_hour_charge_sum_error_kwh':float(np.max(abs(c.reshape(-1,6,24).sum(axis=(1,2))-c.sum(axis=1)))),
            'four_hour_discharge_sum_error_kwh':float(np.max(abs(u.reshape(-1,6,24).sum(axis=(1,2))-u.sum(axis=1)))),
            'slots_per_four_hour_block':24}
        z=checks[name];tol=cfg.PHYSICAL_TOL
        for key in ('balance_max_kwh','state_equation_max_kwh','simultaneous_max_kwh','cross_day_soc_max_kwh',
                    'first_soc_error_kwh','emergency_while_charging_max_kwh','four_hour_charge_sum_error_kwh','four_hour_discharge_sum_error_kwh'):
            assert z[key]<=tol,(name,key,z[key])
        assert s.min()>=1200-tol and s.max()<=10800+tol
        assert c.max()<=cfg.ENERGY_LIMIT+tol and u.max()<=cfg.ENERGY_LIMIT+tol
        assert z['nonfinite_count']==0 and z['negative_min_kwh']>=-tol
    return checks


def validate_causality(data, forecasts, streams, risk_history):
    # 覆盖训练启动后、年中、年末；重新生成预测而非只检查一列索引声明。
    result={}; max_prediction=max_plan=max_margin=0.
    for d in (40,171,354):
        load=data.load[:d+2].copy();pv=data.pv[:d+2].copy()
        load[d:]=load[d:]*3+1000;pv[d:]=pv[d:]*.1
        changed=generate_causal_forecasts(data.dates[:d+2],load,pv)
        for key in ('load_final','pv_final','net_ridge_weight','load_weight_a','pv_weights'):
            max_prediction=max(max_prediction,float(np.max(abs(changed[key][d]-forecasts[key][d]))))
        old=streams['official'][d];alpha,kappa=cfg.RISK_CANDIDATES[0]
        margin1=weighted_safety_margin(d,forecasts['net_error'],alpha)
        margin2=weighted_safety_margin(d,changed['net_error'],alpha)
        max_margin=max(max_margin,float(np.max(abs(margin1-margin2))))
        # 当天、未来实际扰动后，重新形成相同风险候选的计划。
        value=historical_price_value(data.prices[:d],data.prices[d])
        initial=old['actual']['soc'][0]
        plans=[]
        for f,m in ((forecasts,margin1),(changed,margin2)):
            plans.append(solve_plan(f['load_final'][d]-f['pv_final'][d]+kappa*m,data.prices[d],initial,value)['q'])
        max_plan=max(max_plan,float(np.max(abs(plans[0]-plans[1]))))
    result.update(forecast_current_future_actual_perturbation=max_prediction,
        safety_margin_future_error_perturbation=max_margin,plan_current_future_actual_perturbation=max_plan)
    d=171; old=streams['official'][d];prices=data.prices.copy();prices[d+1:]*=9
    value=historical_price_value(prices[:d],prices[d])
    plan=solve_plan(old['demand'],prices[d],old['actual']['soc'][0],value)
    result['plan_future_price_perturbation']=float(np.max(abs(plan['q']-old['plan']['q'])))
    original=execute_day(data.load[d]-data.pv[d],old['plan'],old['point_forecast'],data.prices[d],old['actual']['soc'][0],'mpc')
    revised=execute_day(data.load[d]-data.pv[d],plan,old['point_forecast'],prices[d],old['actual']['soc'][0],'mpc')
    result['execution_future_price_perturbation']=float(max(np.max(abs(original[k]-revised[k])) for k in original))
    actual=data.load[d]-data.pv[d];altered=actual.copy();altered[73:]+=9000
    revised=execute_day(altered,old['plan'],old['point_forecast'],data.prices[d],old['actual']['soc'][0],'mpc')
    result['execution_future_intraday_actual_perturbation']=float(max(np.max(abs(original[k][:73]-revised[k][:73])) for k in ('charge','discharge','emergency','waste')))
    # 调参函数只接收截断的历史；改变未完成日评分不会改变选项。
    histories=[h[:d] for h in risk_history]
    selected,scores=choose_from_history(histories,d,value)
    modified=[[dict(r) for r in h] for h in risk_history]
    for h in modified:
        for r in h[d:]:r['total_cost_yuan']*=100
    selected2,scores2=choose_from_history([h[:d] for h in modified],d,value)
    result['selection_future_score_perturbation']=float(max(abs(np.asarray(scores)-scores2)))
    assert selected==selected2
    # 两段解析例：仅有90kWh可用，后段价格更贵；MPC应把电留给后段。
    q=np.zeros(144);p=np.ones(144);p[-2:]=[1,2];f=np.zeros(144);f[-2:]=90
    action=decide_step(142,90,q,f,p,1300,0,'mpc')
    assert abs(action[1])<=1e-6 and abs(action[2]-90)<=1e-6
    result['mpc_reserves_for_expensive_future_example']='passed'
    assert all(v<=1e-6 for v in result.values() if isinstance(v,float)),result
    return result


def validate_joint_selection(data,streams,daily,selections,combo_history,extra):
    """重建历史排名，并以被扰动的未来输入重放同一历史小窗口。"""
    from .joint_search import COMBINATIONS,replay_scores
    max_score_error=max_initial_error=0.
    for sel in selections:
        d=next(i for i,x in enumerate(data.dates) if str(x)==sel['date'])
        assert sel['history_end']<sel['date'] and sel['history_start']==str(data.dates[d-28])
        rows=[r for r in extra['score_rows'] if r['date']==sel['date'] and r['selector']=='same_start']
        assert len(rows)==12 and sum(r['selected'] for r in rows)==1
        initial=daily['official'][d-28]['soc_start_kwh']
        for r in rows:
            max_initial_error=max(max_initial_error,abs(r['initial_soc_kwh']-initial))
            expected=r['window_cost_yuan']-.9*extra['price_values'][d]*(r['final_soc_kwh']-initial)
            max_score_error=max(max_score_error,abs(expected-r['score']))
        assert sel['combo']==min(rows,key=lambda r:(r['score'],r['combo']))['combo']
        for j in range(d,min(d+7,len(data.dates))):
            expected=COMBINATIONS[sel['combo']]
            assert (daily['official'][j]['risk_index'],daily['official'][j]['controller'])==expected
    # 接口必须截断于决策日前；未来实际/价格的任意扰动不能改变重放分数。
    stop=66;first=64;net=data.load-data.pv;prices=data.prices.copy()
    altered=net.copy();altered[stop:]=altered[stop:]*5+9000;prices[stop:]*=7
    common=(extra['point'][:stop],extra['demands'][:stop],extra['price_values'][:stop],extra['price_values'][stop])
    a=replay_scores(first,stop,6000,net[:stop],data.prices[:stop],*common)
    b=replay_scores(first,stop,6000,altered[:stop],prices[:stop],*common)
    future_error=max(abs(x['score']-y['score']) for x,y in zip(a,b))
    assert max(max_score_error,max_initial_error,future_error)<=1e-6
    return {'candidate_combinations':12,'updates':len(selections),'history_window_days':28,
        'same_start_soc_max_error_kwh':max_initial_error,'score_reconstruction_max_error_yuan':max_score_error,
        'historical_replay_future_perturbation_max_error_yuan':future_error,
        'selected_minimum_history_score':True,'selection_held_until_next_update':True,
        'formal_rule_fixed_before_evaluation':'same_start_joint'}
