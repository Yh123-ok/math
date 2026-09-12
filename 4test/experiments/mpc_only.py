"""Six predeclared risk settings, MPC only; 56-day historical selection.

Run from any directory: python 4test/experiments/mpc_only.py
All shadow trajectories, inventory and scores advance one historical day at a
time. No current/future outcomes are read when selecting today's setting.
"""
from pathlib import Path
import argparse
import csv
import json
import random
import sys

import numpy as np

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
import config as cfg
from src.data_io import read_inputs,interval_label
from src.forecasting import generate_causal_forecasts,weighted_safety_margin
from src.day_ahead import historical_price_value,solve_plan
from src.realtime import execute_day
from src.backtest import daily_record
from src.validation import validate_physics

WINDOW=56
OUT=BASE/'experiments'/'mpc_only_outputs'


def score(rows, start, stop, value):
    history=rows[start:stop]
    assert len(history)==stop-start and all(r['day']<stop for r in history)
    return sum(r['total_cost_yuan'] for r in history) - .9*value*(
        history[-1]['soc_end_kwh']-history[0]['soc_start_kwh'])


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cached-shadows',action='store_true',help='Use input-hash-verified MPC shadow histories from prior full run')
    args=parser.parse_args()
    random.seed(cfg.SEED);np.random.seed(cfg.SEED)
    data=read_inputs(BASE.parent)
    forecasts=generate_causal_forecasts(data.dates,data.load,data.pv)
    actual_net=data.load-data.pv
    point=forecasts['load_final']-forecasts['pv_final']
    shadows=[[] for _ in cfg.RISK_CANDIDATES]
    if args.cached_shadows:
        recorded=json.loads((BASE/'outputs'/'cache_inputs.json').read_text(encoding='utf-8'))
        assert {k:v['sha256'] for k,v in recorded.items()}=={k:v['sha256'] for k,v in data.audit.items()}
        with (BASE/'outputs'/'risk_shadow_daily.csv').open(encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                combo=int(row['combo'])
                if combo%2==1:
                    r=combo//2
                    assert int(row['risk_index'])==r and row['controller']=='mpc'
                    shadows[r].append({k:(int(v) if k in ('day','risk_index') else float(v))
                        for k,v in row.items() if k not in ('combo','date','controller')})
        assert all(len(s)==len(data.dates) and [r['day'] for r in s]==list(range(len(data.dates))) for s in shadows)
    official=[];records=[];selections=[];choice=0
    for d,day in enumerate(data.dates):
        value=historical_price_value(data.prices[:d],data.prices[d])
        if d>=60 and (d-cfg.OFFICIAL_START_INDEX)%cfg.UPDATE_DAYS==0:
            past=[score(rows,d-WINDOW,d,value) for rows in shadows]
            choice=int(np.argmin(past))
            selections.append({'date':str(day),'history_start':str(data.dates[d-WINDOW]),
                'history_end':str(data.dates[d-1]),'risk_index':choice,
                'alpha':cfg.RISK_CANDIDATES[choice][0],
                'kappa':cfg.RISK_CANDIDATES[choice][1],
                **{f'score_{i}':v for i,v in enumerate(past)}})
        demands=[(point[d] if d else np.zeros(144))+k*weighted_safety_margin(
            d,forecasts['net_error'],a) for a,k in cfg.RISK_CANDIDATES]
        cache={}
        def simulate(risk,initial):
            key=(risk,float(initial))
            if key not in cache:
                if d==0:plan={'q':np.zeros(144),'rho':4.5*value,'status':'无历史首日零计划'}
                else:plan=solve_plan(demands[risk],data.prices[d],initial,value)
                actual=execute_day(actual_net[d],plan,point[d] if d else np.zeros(144),
                    data.prices[d],initial,'mpc' if d else 'greedy')
                cache[key]=(plan,actual)
            return cache[key]
        if not args.cached_shadows:
            for risk,rows in enumerate(shadows):
                initial=rows[-1]['soc_end_kwh'] if rows else cfg.SOC_INITIAL
                plan,actual=simulate(risk,initial)
                rows.append(daily_record(d,plan,actual,data.prices[d],risk,'mpc' if d else 'greedy'))
        initial=official[-1]['soc_end_kwh'] if official else cfg.SOC_INITIAL
        plan,actual=simulate(choice,initial)
        official.append(daily_record(d,plan,actual,data.prices[d],choice,'mpc' if d else 'greedy'))
        records.append({'plan':plan,'actual':actual,'demand':demands[choice],
                        'point_forecast':point[d] if d else np.zeros(144)})
        if d%30==0 or d==len(data.dates)-1:print(f'{day} {d+1}/{len(data.dates)}',flush=True)
    checks=validate_physics(data,{'official':records})['official']
    OUT.mkdir(exist_ok=True,parents=True)
    with (OUT/'selections.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(selections[0]));w.writeheader();w.writerows(selections)
    chosen=official[cfg.OFFICIAL_START_INDEX:]
    with (OUT/'daily.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=['date']+list(chosen[0]));w.writeheader()
        for row in chosen:w.writerow({'date':str(data.dates[row['day']]),**row})
    with (OUT/'schedule.csv').open('w',newline='',encoding='utf-8-sig') as f:
        fields=['date','slot','period','price_yuan_per_kwh','load_kwh','pv_kwh','plan_purchase_kwh',
                'charge_kwh','discharge_kwh','emergency_kwh','waste_kwh','soc_start_kwh','soc_end_kwh']
        w=csv.writer(f);w.writerow(fields)
        for d in range(cfg.OFFICIAL_START_INDEX,len(data.dates)):
            a=records[d]['actual'];q=records[d]['plan']['q']
            for t in range(144):w.writerow([str(data.dates[d]),t,interval_label(t),data.prices[d,t],
                data.load[d,t],data.pv[d,t],q[t],a['charge'][t],a['discharge'][t],a['emergency'][t],
                a['waste'][t],a['soc'][t],a['soc'][t+1]])
    summary={'method':'MPC only; 6 predeclared risk pairs; every 7 days select by previous 56 completed days',
        'evaluation_days':len(chosen),'planned_cost_yuan':sum(r['planned_cost_yuan'] for r in chosen),
        'emergency_cost_yuan':sum(r['emergency_cost_yuan'] for r in chosen),
        'total_cost_yuan':sum(r['total_cost_yuan'] for r in chosen),
        'planned_kwh':sum(r['plan_purchase_kwh'] for r in chosen),
        'emergency_kwh':sum(r['emergency_kwh'] for r in chosen),
        'waste_kwh':sum(r['waste_kwh'] for r in chosen),'checks':checks,
        'input_sha256':{k:v['sha256'] for k,v in data.audit.items()}}
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('checks','input_sha256')},ensure_ascii=False),flush=True)


if __name__=='__main__':run()
