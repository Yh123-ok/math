"""One model: historical-error scenario plan plus the existing causal MPC.

Run from any directory: python 4test/experiments/scenario_mpc.py
This experiment writes CSV and a numerical audit; it never edits result4-2.xlsx.
"""
from pathlib import Path
import csv
import json
import random
import sys

import numpy as np

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
import config as cfg
from src.data_io import read_inputs, interval_label
from src.forecasting import generate_causal_forecasts
from src.day_ahead import historical_price_value,solve_plan
from src.scenario_plan import solve_scenario_plan
from src.realtime import execute_day
from src.backtest import daily_record
from src.validation import validate_physics

SCENARIOS=14
OUT=BASE/'experiments'/'scenario_mpc_outputs'


def run():
    random.seed(cfg.SEED);np.random.seed(cfg.SEED)
    data=read_inputs(BASE.parent)
    forecasts=generate_causal_forecasts(data.dates,data.load,data.pv)
    actual_net=data.load-data.pv
    net_forecast=forecasts['load_final']-forecasts['pv_final']
    streams=[]; daily=[]
    for d,day in enumerate(data.dates):
        initial=daily[-1]['soc_end_kwh'] if daily else cfg.SOC_INITIAL
        value=historical_price_value(data.prices[:d],data.prices[d])
        rho=cfg.EMERGENCY_MULTIPLIER*cfg.ETA_DISCHARGE*value
        if d==0:
            plan={'q':np.zeros(144),'rho':rho,'status':'无历史首日零正常计划'}
        elif d<8:
            # Retain a simple, predeclared cold start until complete residual
            # paths are available; never use current/future actual demand.
            plan=solve_plan(net_forecast[d],data.prices[d],initial,value)
        else:
            errors=forecasts['net_error'][max(1,d-SCENARIOS):d].copy()
            assert len(errors)==min(SCENARIOS,d-1)
            plan=solve_scenario_plan(net_forecast[d],errors,data.prices[d],initial,rho)
        actual=execute_day(actual_net[d],plan,net_forecast[d] if d else np.zeros(144),
                           data.prices[d],initial,'mpc' if d else 'greedy')
        streams.append({'plan':plan,'actual':actual,'demand':net_forecast[d],
                        'point_forecast':net_forecast[d]})
        daily.append(daily_record(d,plan,actual,data.prices[d],0,'mpc' if d else 'greedy'))
        if d%14==0 or d==len(data.dates)-1:
            print(f'{day}  {d+1}/{len(data.dates)}',flush=True)
    checks=validate_physics(data,{'scenario_mpc':streams})['scenario_mpc']
    OUT.mkdir(parents=True,exist_ok=True)
    rows=daily[cfg.OFFICIAL_START_INDEX:]
    with (OUT/'daily.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=['date']+list(rows[0]));w.writeheader()
        for r in rows:w.writerow({'date':str(data.dates[r['day']]),**r})
    with (OUT/'schedule.csv').open('w',newline='',encoding='utf-8-sig') as f:
        fields=['date','slot','period','price_yuan_per_kwh','load_kwh','pv_kwh','plan_purchase_kwh',
                'charge_kwh','discharge_kwh','emergency_kwh','waste_kwh','soc_start_kwh','soc_end_kwh']
        w=csv.writer(f);w.writerow(fields)
        for d in range(cfg.OFFICIAL_START_INDEX,len(data.dates)):
            a=streams[d]['actual'];q=streams[d]['plan']['q']
            for t in range(144):
                w.writerow([data.dates[d],t,interval_label(t),data.prices[d,t],data.load[d,t],data.pv[d,t],
                            q[t],a['charge'][t],a['discharge'][t],a['emergency'][t],a['waste'][t],
                            a['soc'][t],a['soc'][t+1]])
    summary={'method':'14 prior-day full residual paths, scenario LP, existing causal MPC',
             'days':len(rows),'planned_cost_yuan':sum(r['planned_cost_yuan'] for r in rows),
             'emergency_cost_yuan':sum(r['emergency_cost_yuan'] for r in rows),
             'total_cost_yuan':sum(r['total_cost_yuan'] for r in rows),
             'emergency_kwh':sum(r['emergency_kwh'] for r in rows),
             'planned_kwh':sum(r['plan_purchase_kwh'] for r in rows),
             'waste_kwh':sum(r['waste_kwh'] for r in rows),
             'checks':checks,'input_sha256':{k:v['sha256'] for k,v in data.audit.items()}}
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('checks','input_sha256')},ensure_ascii=False),flush=True)


if __name__=='__main__':run()
