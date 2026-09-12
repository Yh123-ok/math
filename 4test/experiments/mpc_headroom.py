"""Read-only hindsight bound: maximum MPC improvement with ORIGINAL q and day endpoints.

Uses future actual demand strictly for retrospective diagnosis, never for a plan
or real-time action. Run: python 4test/experiments/mpc_headroom.py.
"""
from pathlib import Path
import json
import pickle
import sys

import numpy as np
from scipy.optimize import linprog

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from src.data_io import read_inputs
from src.realtime import horizon_matrix
from src.day_ahead import historical_price_value


def main():
    data = read_inputs(BASE.parent)
    out = BASE / 'outputs'
    recorded = json.loads((out / 'cache_inputs.json').read_text(encoding='utf-8'))
    assert {k:v['sha256'] for k,v in recorded.items()} == {k:v['sha256'] for k,v in data.audit.items()}
    with (out / 'joint_run_cache.pkl').open('rb') as f:
        _, streams, _, _, _, _, _ = pickle.load(f)
    baseline = streams['mpc']
    assert len(baseline) == len(data.dates)
    costs = []
    gains = []
    eq, _ = horizon_matrix(144)
    for d in range(31, len(data.dates)):
        record = baseline[d]
        q = record['plan']['q']
        actual = record['actual']
        gaps = data.load[d] - data.pv[d] - q
        surplus = np.minimum(np.maximum(-gaps, 0.), 5000/6)
        deficits = np.minimum(np.maximum(gaps, 0.), 5000/6)
        p = data.prices[d]
        n = 144
        obj = np.r_[np.zeros(n), -5*p, np.zeros(n+2)]
        bounds = [(0, float(x)) for x in surplus] + [(0, float(x)) for x in deficits]
        bounds += [(1200, 10800)]*(n+1) + [(0,0)]
        bounds[2*n] = (float(actual['soc'][0]),)*2
        bounds[3*n] = (float(actual['soc'][-1]),)*2
        solved = linprog(obj, A_eq=eq, b_eq=np.zeros(n), bounds=bounds, method='highs')
        if not solved.success: raise RuntimeError(f'{data.dates[d]}: {solved.message}')
        existing = float(np.dot(5*p, actual['emergency']))
        hindsight = float(np.dot(5*p, np.maximum(gaps,0) - solved.x[n:2*n]))
        assert hindsight <= existing+1e-5
        costs.append(existing); gains.append(existing-hindsight)
    summary = {'description': 'HINDSIGHT lower bound only. No future actual enters a policy.',
               'same_locked_plan': True, 'same_daily_initial_and_final_soc': True,
               'days': len(costs), 'mpc_emergency_fee_yuan': sum(costs),
               'hindsight_min_emergency_fee_yuan': sum(costs)-sum(gains),
               'max_possible_mpc_only_saving_yuan': sum(gains)}
    dest = BASE / 'experiments' / 'mpc_direct_outputs' / 'headroom.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
