"""逐日推进的历史回测：影子策略各自延续库存，正式策略绝不重置库存。"""
import numpy as np
import config as cfg
from .forecasting import weighted_safety_margin
from .day_ahead import solve_plan, historical_price_value
from .realtime import execute_day


def history_score(rows, day, price_value):
    """只取已完成日；库存变化以同一历史代理价计值，减少耗空电池的偏好。"""
    past = rows[max(0, day-cfg.SCORE_DAYS):day]
    assert len(rows) == day
    return sum(r['total_cost_yuan'] for r in past) - .9*price_value*(past[-1]['soc_end_kwh']-past[0]['soc_start_kwh'])


def choose_from_history(histories, day, price_value):
    scores = [history_score(h, day, price_value) for h in histories]
    return int(np.argmin(scores)), scores


def daily_record(day, plan, actual, prices, risk, mode):
    normal=float(np.dot(prices, plan['q']))
    urgent=float(np.dot(5*prices, actual['emergency']))
    return {'day':day,'risk_index':risk,'controller':mode,
        'plan_purchase_kwh':float(plan['q'].sum()),'emergency_kwh':float(actual['emergency'].sum()),
        'charge_kwh':float(actual['charge'].sum()),'discharge_kwh':float(actual['discharge'].sum()),
        'waste_kwh':float(actual['waste'].sum()),'soc_start_kwh':float(actual['soc'][0]),
        'soc_end_kwh':float(actual['soc'][-1]),'planned_cost_yuan':normal,
        'emergency_cost_yuan':urgent,'total_cost_yuan':normal+urgent}


def run_backtest(data, forecasts):
    n=len(data.dates); actual_net=data.load-data.pv
    risk_history=[[] for _ in cfg.RISK_CANDIDATES]
    streams={name:[] for name in ('greedy','mpc','official')}
    daily={name:[] for name in streams}
    selections=[]; risk=controller=0
    for d in range(n):
        value=historical_price_value(data.prices[:d],data.prices[d])
        update=d>=cfg.COLD_START_DAYS and (d-cfg.OFFICIAL_START_INDEX)%cfg.UPDATE_DAYS==0
        if update:
            risk,scores=choose_from_history(risk_history,d,value)
            controller,cs=choose_from_history([daily['greedy'],daily['mpc']],d,value)
            selections.append({'date':str(data.dates[d]),'history_start':str(data.dates[max(0,d-cfg.SCORE_DAYS)]),
                'history_end':str(data.dates[d-1]),'risk_index':risk,'alpha':cfg.RISK_CANDIDATES[risk][0],
                'kappa':cfg.RISK_CANDIDATES[risk][1],'controller':('greedy','mpc')[controller],
                **{f'risk_score_{j}':s for j,s in enumerate(scores)},'greedy_score':cs[0],'mpc_score':cs[1]})
        demands=[]
        base=np.zeros(144) if d==0 else forecasts['load_final'][d]-forecasts['pv_final'][d]
        for alpha,kappa in cfg.RISK_CANDIDATES:
            demands.append(base+kappa*weighted_safety_margin(d,forecasts['net_error'],alpha))
        cache={}
        def simulate(j, initial, mode):
            key=(j,initial,mode)
            if key not in cache:
                if d==0:
                    plan={'q':np.zeros(144),'rho':4.5*value,'price_value':value,'status':'无历史首日：零计划、实时保供'}
                else: plan=solve_plan(demands[j],data.prices[d],initial,value)
                # MPC未来输入用点预测；安全余量已体现在锁定购电计划中，不重复叠加。
                actual=execute_day(actual_net[d],plan,base,data.prices[d],initial,mode if d else 'greedy')
                cache[key]=(plan,actual)
            return cache[key]
        for j,history in enumerate(risk_history):
            initial=history[-1]['soc_end_kwh'] if history else cfg.SOC_INITIAL
            plan,actual=simulate(j,initial,'greedy')
            history.append(daily_record(d,plan,actual,data.prices[d],j,'greedy'))
        for name in streams:
            mode=('greedy','mpc')[controller] if name=='official' else name
            initial=daily[name][-1]['soc_end_kwh'] if d else cfg.SOC_INITIAL
            plan,actual=simulate(risk,initial,mode)
            streams[name].append({'plan':plan,'actual':actual,'demand':demands[risk],'point_forecast':base})
            daily[name].append(daily_record(d,plan,actual,data.prices[d],risk,mode))
        if d%14==0 or d==n-1:
            print(f'{data.dates[d]} 完成；风险候选={risk}，控制器={daily["official"][-1]["controller"]}',flush=True)
    return streams,daily,selections,risk_history
