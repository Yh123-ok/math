"""Simple, causal candidate: January-only model choice + fixed 80% risk + MPC.

Run: python 4test/experiments/simple_mpc.py
The 80% level follows the known 5x emergency tariff. No retrospective tuning.
"""
from pathlib import Path
import csv,json,random,sys
import numpy as np
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
import config as cfg
from src.data_io import read_inputs,interval_label
from src.forecasting import generate_causal_forecasts,weighted_safety_margin
from src.simple_load_forecast import forecast_load
from src.day_ahead import historical_price_value,solve_plan
from src.realtime import execute_day
from src.backtest import daily_record
from src.validation import validate_physics
OUT=BASE/'experiments'/'simple_mpc_outputs'


def run():
    random.seed(cfg.SEED);np.random.seed(cfg.SEED)
    data=read_inputs(BASE.parent)
    previous=generate_causal_forecasts(data.dates,data.load,data.pv)
    candidate_load=forecast_load(data.dates,data.load)
    # This choice is made at 2025-02-01 00:00, using only completed January
    # days. During January the original predictor remains active, so the
    # initial inventory and historical residuals are never retroactively
    # altered by a choice that did not yet exist.
    calibration=slice(14,cfg.OFFICIAL_START_INDEX)
    original_mae=float(np.mean(abs(previous['load_final'][calibration]-data.load[calibration])))
    candidate_mae=float(np.mean(abs(candidate_load[calibration]-data.load[calibration])))
    choose_simple=candidate_mae<original_mae
    predicted_load=previous['load_final'].copy()
    if choose_simple:predicted_load[cfg.OFFICIAL_START_INDEX:]=candidate_load[cfg.OFFICIAL_START_INDEX:]
    predicted_pv=previous['pv_final']
    point=predicted_load-predicted_pv
    actual_net=data.load-data.pv
    error=actual_net-point
    daily=[];records=[]
    for d,day in enumerate(data.dates):
        initial=daily[-1]['soc_end_kwh'] if daily else cfg.SOC_INITIAL
        value=historical_price_value(data.prices[:d],data.prices[d])
        margin=weighted_safety_margin(d,error,.8)
        demand=(point[d] if d else np.zeros(144))+margin
        if d==0:plan={'q':np.zeros(144),'rho':4.5*value,'status':'无历史首日零计划'}
        else:plan=solve_plan(demand,data.prices[d],initial,value)
        actual=execute_day(actual_net[d],plan,point[d] if d else np.zeros(144),
                           data.prices[d],initial,'mpc' if d else 'greedy')
        daily.append(daily_record(d,plan,actual,data.prices[d],0,'mpc' if d else 'greedy'))
        records.append({'plan':plan,'actual':actual,'demand':demand,'point_forecast':point[d]})
        if d%30==0 or d==len(data.dates)-1:print(f'{day} {d+1}/{len(data.dates)}',flush=True)
    checks=validate_physics(data,{'simple_mpc':records})['simple_mpc']
    OUT.mkdir(parents=True,exist_ok=True)
    selected=daily[cfg.OFFICIAL_START_INDEX:]
    with (OUT/'daily.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=['date']+list(selected[0]));w.writeheader()
        for r in selected:w.writerow({'date':str(data.dates[r['day']]),**r})
    with (OUT/'schedule.csv').open('w',newline='',encoding='utf-8-sig') as f:
        fields=['date','slot','period','price_yuan_per_kwh','load_kwh','pv_kwh','plan_purchase_kwh',
                'charge_kwh','discharge_kwh','emergency_kwh','waste_kwh','soc_start_kwh','soc_end_kwh']
        w=csv.writer(f);w.writerow(fields)
        for d in range(cfg.OFFICIAL_START_INDEX,len(data.dates)):
            a=records[d]['actual'];q=records[d]['plan']['q']
            for t in range(144):w.writerow([str(data.dates[d]),t,interval_label(t),data.prices[d,t],
                data.load[d,t],data.pv[d,t],q[t],a['charge'][t],a['discharge'][t],a['emergency'][t],
                a['waste'][t],a['soc'][t],a['soc'][t+1]])
    sl=slice(cfg.OFFICIAL_START_INDEX,None)
    summary={'method':'January-only load-model choice; fixed 80% historical residual margin; original PV; MPC',
        'predictor_selected_at':'2025-02-01 00:00','chosen_predictor':'daily_shape' if choose_simple else 'original',
        'january_original_load_mae_kwh':original_mae,
        'january_daily_shape_load_mae_kwh':candidate_mae,
        'evaluation_days':len(selected),'planned_cost_yuan':sum(r['planned_cost_yuan'] for r in selected),
        'emergency_cost_yuan':sum(r['emergency_cost_yuan'] for r in selected),
        'total_cost_yuan':sum(r['total_cost_yuan'] for r in selected),
        'planned_kwh':sum(r['plan_purchase_kwh'] for r in selected),
        'emergency_kwh':sum(r['emergency_kwh'] for r in selected),
        'waste_kwh':sum(r['waste_kwh'] for r in selected),
        'load_mae_kwh':float(np.mean(np.abs(predicted_load[sl]-data.load[sl]))),
        'net_mae_kwh':float(np.mean(np.abs(point[sl]-actual_net[sl]))),
        'checks':checks,'input_sha256':{k:v['sha256'] for k,v in data.audit.items()}}
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('checks','input_sha256')},ensure_ascii=False),flush=True)


if __name__=='__main__':run()
