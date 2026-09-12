"""12组合联合选择与同库存起点重放；所有评分窗口严格结束于决策日前。"""
import time
import numpy as np
import config as cfg
from .backtest import daily_record, history_score, run_backtest as run_layered
from .day_ahead import historical_price_value, solve_plan
from .forecasting import weighted_safety_margin
from .realtime import execute_day

COMBINATIONS=tuple((risk,mode) for risk in range(len(cfg.RISK_CANDIDATES)) for mode in ('greedy','mpc'))


def prepare_forecast_demands(forecasts, days):
    """一次保存各日当时的预测与余量。后续历史重放不重估过去的预测。"""
    point=np.zeros((days,144));point[1:]=forecasts['load_final'][1:days]-forecasts['pv_final'][1:days]
    demands=np.empty((days,len(cfg.RISK_CANDIDATES),144))
    for d in range(days):
        for r,(alpha,kappa) in enumerate(cfg.RISK_CANDIDATES):
            demands[d,r]=point[d]+kappa*weighted_safety_margin(d,forecasts['net_error'],alpha)
    return point,demands


def simulate_one_day(d,combo,initial,actual_net,prices,point,demands,price_values,cache=None):
    key=(d,combo,float(initial))
    if cache is not None and key in cache:return cache[key]
    risk,mode=COMBINATIONS[combo]
    if d==0:
        plan={'q':np.zeros(144),'rho':4.5*price_values[d],'price_value':price_values[d],'status':'无历史首日零计划'}
    else:
        plan=solve_plan(demands[d,risk],prices[d],initial,price_values[d])
    actual=execute_day(actual_net[d],plan,point[d],prices[d],initial,mode if d else 'greedy')
    record={'plan':plan,'actual':actual,'demand':demands[d,risk],'point_forecast':point[d]}
    answer=(record,daily_record(d,plan,actual,prices[d],risk,mode))
    if cache is not None:cache[key]=answer
    return answer


def replay_scores(start,stop,initial,actual_history,price_history,point_history,demand_history,value_history,inventory_price,cache=None):
    """接口只接收截至stop-1的历史，stop是排他的决策日索引。"""
    assert len(actual_history)==len(price_history)==len(point_history)==len(demand_history)==len(value_history)==stop
    assert 0<=start<stop
    details=[]
    for combo in range(len(COMBINATIONS)):
        soc=float(initial);bill=urgent=0.
        for d in range(start,stop):
            _,row=simulate_one_day(d,combo,soc,actual_history,price_history,point_history,demand_history,value_history,cache)
            soc=row['soc_end_kwh'];bill+=row['total_cost_yuan'];urgent+=row['emergency_kwh']
        adjustment=.9*inventory_price*(soc-initial)
        details.append({'combo':combo,'score':bill-adjustment,'window_cost_yuan':bill,
            'window_emergency_kwh':urgent,'initial_soc_kwh':initial,'final_soc_kwh':soc,
            'inventory_credit_yuan':adjustment})
    return details


def selection_record(data,d,combo,details,selector):
    risk,mode=COMBINATIONS[combo];ordered=sorted(r['score'] for r in details)
    return {'date':str(data.dates[d]),'history_start':str(data.dates[d-cfg.SCORE_DAYS]),
        'history_end':str(data.dates[d-1]),'selector':selector,'combo':combo,'risk_index':risk,
        'alpha':cfg.RISK_CANDIDATES[risk][0],'kappa':cfg.RISK_CANDIDATES[risk][1],
        'controller':mode,'best_score':ordered[0],'runner_up_gap_yuan':ordered[1]-ordered[0],
        **{f'combo_score_{r["combo"]}':r['score'] for r in details}}


def run_joint_backtest(data,forecasts):
    """正式规则预先固定为同起点联合选择，不在全年结束后挑赢家。"""
    start_clock=time.perf_counter()
    old_streams,old_daily,old_selections,_=run_layered(data,forecasts)
    streams={'greedy':old_streams['greedy'],'mpc':old_streams['mpc'],'layered':old_streams['official'],
        'joint':[],'official':[]}
    daily={'greedy':old_daily['greedy'],'mpc':old_daily['mpc'],'layered':old_daily['official'],
        'joint':[],'official':[]}
    n=len(data.dates);point,demands=prepare_forecast_demands(forecasts,n)
    actual_net=data.load-data.pv
    values=np.array([historical_price_value(data.prices[:d],data.prices[d]) for d in range(n)])
    combo_history=[[] for _ in COMBINATIONS]
    for combo in range(len(COMBINATIONS)):streams[f'shadow_{combo:02d}']=[]
    selections=[];joint_selections=[];score_rows=[];joint_combo=official_combo=0
    # 只在本次固定输入回测内复用完全相同的日/组合/初始库存，不舍入库存。
    simulation_cache={}
    for d in range(n):
        update=d>=cfg.COLD_START_DAYS and (d-cfg.OFFICIAL_START_INDEX)%cfg.UPDATE_DAYS==0
        if update:
            first=d-cfg.SCORE_DAYS
            continuous=[]
            for combo,rows in enumerate(combo_history):
                past=rows[first:d];cost=sum(r['total_cost_yuan'] for r in past)
                credit=.9*values[d]*(past[-1]['soc_end_kwh']-past[0]['soc_start_kwh'])
                continuous.append({'combo':combo,'score':history_score(rows,d,values[d]),'window_cost_yuan':cost,
                    'window_emergency_kwh':sum(r['emergency_kwh'] for r in past),
                    'initial_soc_kwh':past[0]['soc_start_kwh'],'final_soc_kwh':past[-1]['soc_end_kwh'],
                    'inventory_credit_yuan':credit})
            joint_combo=int(np.argmin([r['score'] for r in continuous]))
            # 使用正式策略在28日前的已知真实模拟库存，所有候选同一起点。
            initial=daily['official'][first]['soc_start_kwh']
            simulation_cache={k:v for k,v in simulation_cache.items() if k[0]>=first}
            replay=replay_scores(first,d,initial,actual_net[:d],data.prices[:d],point[:d],demands[:d],values[:d],values[d],simulation_cache)
            official_combo=int(np.argmin([r['score'] for r in replay]))
            selections.append(selection_record(data,d,official_combo,replay,'same_start'))
            joint_selections.append(selection_record(data,d,joint_combo,continuous,'continuous'))
            for selector,details,winner in [('same_start',replay,official_combo),('continuous',continuous,joint_combo)]:
                for r in details:
                    risk,mode=COMBINATIONS[r['combo']]
                    score_rows.append({'date':str(data.dates[d]),'selector':selector,
                        'history_start':str(data.dates[first]),'history_end':str(data.dates[d-1]),
                        'risk_index':risk,'controller':mode,'selected':int(r['combo']==winner),**r})
            print(f'{data.dates[d]} 历史窗口重放完成：连续联合={joint_combo}，同起点联合={official_combo}；累计{time.perf_counter()-start_clock:.0f}秒',flush=True)
        cache={}
        def simulate(combo,initial):
            key=(combo,initial)
            if key not in cache:cache[key]=simulate_one_day(d,combo,initial,actual_net,data.prices,point,demands,values,simulation_cache)
            return cache[key]
        for combo,rows in enumerate(combo_history):
            initial=rows[-1]['soc_end_kwh'] if rows else cfg.SOC_INITIAL
            record,row=simulate(combo,initial);rows.append(row);streams[f'shadow_{combo:02d}'].append(record)
        for name,combo in [('joint',joint_combo),('official',official_combo)]:
            initial=daily[name][-1]['soc_end_kwh'] if d else cfg.SOC_INITIAL
            record,row=simulate(combo,initial);streams[name].append(record);daily[name].append(row)
        if d%28==0:print(f'{data.dates[d]} 联合调度完成',flush=True)
    extra={'joint_selections':joint_selections,'score_rows':score_rows,'layered_selections':old_selections,
        'elapsed_seconds':time.perf_counter()-start_clock,'point':point,'demands':demands,'price_values':values}
    return streams,daily,selections,combo_history,extra
