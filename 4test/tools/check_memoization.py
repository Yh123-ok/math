"""验证跨重叠历史窗口复用LP结果不会改变12组合评分。"""
from pathlib import Path
import sys,json,time
import numpy as np
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from src.data_io import read_inputs
from src.forecasting import generate_causal_forecasts
from src.day_ahead import historical_price_value
from src.joint_search import prepare_forecast_demands,replay_scores


def main():
    data=read_inputs(BASE.parent)
    f=generate_causal_forecasts(data.dates[:40],data.load[:40],data.pv[:40])
    point,demands=prepare_forecast_demands(f,40)
    price=data.prices[:40];net=data.load[:40]-data.pv[:40]
    values=np.array([historical_price_value(price[:d],price[d]) for d in range(40)])
    cache={};maximum=0.;cold_time=warm_time=0.
    for first,stop in [(31,36),(32,37)]:
        args=(first,stop,6000,net[:stop],price[:stop],point[:stop],demands[:stop],values[:stop],values[stop])
        start=time.perf_counter();plain=replay_scores(*args);cold_time+=time.perf_counter()-start
        start=time.perf_counter();memo=replay_scores(*args,cache=cache);warm_time+=time.perf_counter()-start
        for a,b in zip(plain,memo):
            for key in ('score','window_cost_yuan','window_emergency_kwh','final_soc_kwh'):
                maximum=max(maximum,abs(a[key]-b[key]))
    assert maximum<=1e-6
    result={'overlapping_windows':2,'combinations_per_window':12,'max_numeric_difference':maximum,
        'uncached_seconds':cold_time,'cached_seconds':warm_time,'cached_distinct_day_states':len(cache),
        'cache_key':'exact day, combination, initial SOC; one fixed-input run only'}
    (BASE/'outputs/memoization_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
