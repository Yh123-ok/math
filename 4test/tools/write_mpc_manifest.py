"""Hash the exact official artifacts for repository/download verification."""
from pathlib import Path
import hashlib,json,platform
BASE=Path(__file__).resolve().parents[1]


def main():
    summary=json.loads((BASE/'outputs'/'official_summary.json').read_text(encoding='utf-8'))
    names=['README.md','requirements.txt','config.py','main.py','result4-2.xlsx',
        'src/data_io.py','src/forecasting.py','src/simple_load_forecast.py',
        'src/day_ahead.py','src/realtime.py','src/backtest.py','src/validation.py',
        'src/plot_mpc.py','experiments/simple_mpc.py','experiments/finalize_mpc.py',
        'tools/write_result.mjs','tools/audit_mpc_information.py',
        'tools/build_mpc_notebook.py','tools/reproduce_mpc_notebook.py',
        'tools/write_mpc_report.py','tools/write_mpc_manifest.py',
        'notebooks/mpc_analysis.ipynb','reports/METHOD.md','reports/RESULTS_REPORT.md',
        'outputs/official_schedule.csv','outputs/official_daily.csv',
        'outputs/official_summary.json','outputs/official_forecasts.csv',
        'outputs/official_audit.json','outputs/official_causality.json',
        'outputs/mpc_notebook_check.json','outputs/time_mapping.csv']
    names.extend(f'figures/{stem}.{suffix}' for stem in
        ('cost_comparison','monthly_cost_emergency','forecast_accuracy','dispatch_june21')
        for suffix in ('pdf','png'))
    digests={name:hashlib.sha256((BASE/name).read_bytes()).hexdigest() for name in names}
    manifest={'python':platform.python_version(),'inputs_sha256':summary['input_sha256'],
              'artifact_sha256':digests}
    (BASE/'outputs'/'official_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'正式文件哈希清单：{len(digests)}项',flush=True)


if __name__=='__main__':main()
