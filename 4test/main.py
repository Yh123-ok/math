"""入口：python 4test/main.py。默认重新计算、导出、绘图并验收全部结果。"""
from pathlib import Path
import argparse, json, pickle, random, sys, time
import numpy as np
import config as cfg
from src.data_io import read_inputs
from src.forecasting import generate_causal_forecasts
from src.backtest import run_backtest
from src.validation import validate_physics, validate_causality

BASE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compute-only',action='store_true',help='只计算及验证，暂不导出Excel/PDF')
    parser.add_argument('--export-only',action='store_true',help='从本机此次计算缓存重新导出，不重新求解')
    args=parser.parse_args()
    out=BASE/'outputs';out.mkdir(exist_ok=True)
    random.seed(cfg.SEED);np.random.seed(cfg.SEED)
    start=time.perf_counter();data=read_inputs(BASE.parent)
    (out/'input_audit.json').write_text(json.dumps(data.audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(data.audit,ensure_ascii=False,indent=2),flush=True)
    cache=out/'local_run_cache.pkl'
    if args.export_only:
        # pickle仅限本程序在本机生成的可信缓存，正式复现请运行默认命令。
        assert json.loads((out/'cache_inputs.json').read_text(encoding='utf-8'))==data.audit, '输入与缓存不一致，请完整重算'
        with cache.open('rb') as f:forecasts,streams,daily,selections,risk_history,checks=pickle.load(f)
    else:
        forecasts=generate_causal_forecasts(data.dates,data.load,data.pv)
        streams,daily,selections,risk_history=run_backtest(data,forecasts)
        checks={'physical':validate_physics(data,streams),
            'causality':validate_causality(data,forecasts,streams,risk_history)}
        with cache.open('wb') as f:pickle.dump((forecasts,streams,daily,selections,risk_history,checks),f)
        (out/'cache_inputs.json').write_text(json.dumps(data.audit,ensure_ascii=False),encoding='utf-8')
        (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    from src.reporting import export_results
    export_results(BASE,data,forecasts,streams,daily,selections,risk_history,checks,make_artifacts=not args.compute_only)
    print(f'完成，用时 {time.perf_counter()-start:.1f} 秒',flush=True)


if __name__=='__main__': main()
