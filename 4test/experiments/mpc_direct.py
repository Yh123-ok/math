"""Single causal MPC experiment; run: python 4test/experiments/mpc_direct.py.

Keeps the existing forecast and physical model. One fixed risk rule replaces the
six-pair selector; the inventory penalty values next-day replacement energy at a
normal historical price. Does not modify the submitted result4-2.xlsx.
"""
from pathlib import Path
import csv
import json
import random
import sys

import numpy as np

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
import config as cfg
from src.data_io import read_inputs
from src.forecasting import generate_causal_forecasts, weighted_safety_margin
from src.day_ahead import solve_plan, historical_price_value
from src.realtime import execute_day
from src.backtest import daily_record
from src.validation import validate_physics

ALPHA = 0.80
KAPPA = 0.50
TERMINAL_MULTIPLIER = 1.0


def run():
    random.seed(cfg.SEED)
    np.random.seed(cfg.SEED)
    data = read_inputs(BASE.parent)
    forecasts = generate_causal_forecasts(data.dates, data.load, data.pv)
    streams, daily = [], []
    actual_net = data.load - data.pv
    for d, day in enumerate(data.dates):
        value = historical_price_value(data.prices[:d], data.prices[d])
        point = (forecasts['load_final'][d] - forecasts['pv_final'][d]) if d else np.zeros(144)
        # weighted_safety_margin reads only net_error[:d]. Today's and future
        # actual values are passed solely to execute_day's sequential feedback.
        margin = weighted_safety_margin(d, forecasts['net_error'], ALPHA)
        demand = point + KAPPA * margin
        initial = daily[-1]['soc_end_kwh'] if daily else cfg.SOC_INITIAL
        if d == 0:
            plan = {'q': np.zeros(144), 'rho': TERMINAL_MULTIPLIER * cfg.ETA_DISCHARGE * value,
                    'price_value': value, 'status': 'No history: zero normal plan'}
        else:
            plan = solve_plan(demand, data.prices[d], initial, value,
                              terminal_multiplier=TERMINAL_MULTIPLIER)
        actual = execute_day(actual_net[d], plan, point, data.prices[d], initial, 'mpc' if d else 'greedy')
        streams.append({'plan': plan, 'actual': actual, 'demand': demand, 'point_forecast': point})
        daily.append(daily_record(d, plan, actual, data.prices[d], 0, 'mpc' if d else 'greedy'))
        if d % 30 == 0 or d == len(data.dates) - 1:
            print(f'{day}: {d+1}/{len(data.dates)}', flush=True)
    checks = validate_physics(data, {'mpc_direct': streams})['mpc_direct']
    base = [row for row in daily if row['day'] >= cfg.OFFICIAL_START_INDEX]
    out = BASE / 'experiments' / 'mpc_direct_outputs'
    out.mkdir(parents=True, exist_ok=True)
    fields = ['date', 'slot', 'period', 'price', 'load', 'pv', 'plan', 'charge',
              'discharge', 'emergency', 'waste', 'soc_start', 'soc_end']
    with (out / 'schedule.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f); w.writerow(fields)
        for d in range(cfg.OFFICIAL_START_INDEX, len(data.dates)):
            record = streams[d]; a = record['actual']
            for t in range(144):
                w.writerow([data.dates[d], t, f'{t//6:02d}:{(t%6)*10:02d}-{(t+1)//6:02d}:{((t+1)%6)*10:02d}',
                            data.prices[d,t], data.load[d,t], data.pv[d,t], record['plan']['q'][t],
                            a['charge'][t], a['discharge'][t], a['emergency'][t], a['waste'][t],
                            a['soc'][t], a['soc'][t+1]])
    with (out / 'daily.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['date'] + list(base[0])); w.writeheader()
        for r in base: w.writerow({'date': data.dates[r['day']], **r})
    summary = {'model': 'fixed alpha=0.8 kappa=0.5, historical normal-price terminal value, MPC',
               'evaluation_start': str(data.dates[cfg.OFFICIAL_START_INDEX]),
               'evaluation_end': str(data.dates[-1]),
               'official_days': len(base),
               'planned_cost_yuan': sum(r['planned_cost_yuan'] for r in base),
               'emergency_cost_yuan': sum(r['emergency_cost_yuan'] for r in base),
               'total_cost_yuan': sum(r['total_cost_yuan'] for r in base),
               'plan_purchase_kwh': sum(r['plan_purchase_kwh'] for r in base),
               'emergency_kwh': sum(r['emergency_kwh'] for r in base),
               'waste_kwh': sum(r['waste_kwh'] for r in base),
               'checks': checks,
               'input_sha256': {k: v['sha256'] for k,v in data.audit.items()}}
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('checks','input_sha256')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    run()
