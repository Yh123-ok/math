#问题三/问题四-3共享参数网格搜索
import csv
import json
from pathlib import Path
import dispatch_core as core

def run(base_dir, problem):
    base_dir = Path(base_dir).resolve()
    core.configure(base_dir, problem)
    # 先生成全年预测；只用 1 月 8—31 日这段历史回放选参数
    dates, price_all, cold_load, pv_power, load, pv, forecast_map = core.read_inputs()
    load_hat = core.build_load_forecast(dates, load, cold_load)
    pv_hat = core.build_pv_forecast(dates, pv_power, forecast_map)
    startup_margins = core.build_safety_margins(
        dates, load, pv, load_hat, pv_hat, core.STARTUP_BETA
    )
    average_price = float(price_all.mean())
    day_index = {day: i for i, day in enumerate(dates)}
    warmup = core.simulate_range(
        core.Scheduler(price_all[0]), range(core.WARMUP_END_INDEX), dates, price_all,
        load, pv, load_hat, pv_hat, startup_margins, core.INITIAL_SOC,
        core.LPParameters(core.STARTUP_TARGET, core.STARTUP_RHO_MULTIPLIER * average_price),
    )
    config = json.loads((base_dir / f"problem{problem}_config.json").read_text("utf-8"))
    rows = []
    # 逐一尝试“安全分位数、末端 SOC 目标、惩罚系数”三组参数
    for beta in config["safety_quantile_grid"]:
        margins = core.build_safety_margins(dates, load, pv, load_hat, pv_hat, beta)
        for target in config["terminal_target_grid_kwh"]:
            for multiplier in config["rho_multiplier_grid"]:
                params = core.LPParameters(float(target), float(multiplier) * average_price)
                results = core.simulate_range(
                    core.Scheduler(price_all[0]),
                    range(core.WARMUP_END_INDEX, core.EVALUATION_START_INDEX),
                    dates, price_all, load, pv, load_hat, pv_hat, margins,
                    warmup[-1].s_end, params,
                )
                cost = sum(core.settlement(result, price_all[day_index[result.day]])
                           for result in results)
                # 用期末储能残值修正评分，避免只追求短期购电费
                score = cost - config["salvage_rate_multiplier"] * average_price * results[-1].s_end
                rows.append([beta, target, multiplier, cost, results[-1].s_end, score])

    rows.sort(key=lambda row: row[-1])  # 评分越小越好
    output = base_dir / "calibration.csv"
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["safety_quantile", "terminal_target_kwh", "rho_multiplier",
                         "calibration_cost_yuan", "end_soc_kwh", "corrected_score_yuan"])
        writer.writerows(rows)
    frozen = {
        "safety_quantile": rows[0][0],
        "terminal_target_kwh": rows[0][1],
        "rho_multiplier": rows[0][2],
        "rho_yuan_per_kwh": rows[0][2] * average_price,
        "calibration_start": "2025-01-08",
        "calibration_end": "2025-01-31",
        "selection_metric": "actual_cost - salvage_rate_multiplier * mean_price * end_soc",
    }
    (base_dir / "frozen_parameters.json").write_text(
        json.dumps(frozen, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"最优参数: beta={rows[0][0]}, terminal_target={rows[0][1]}, rho_multiplier={rows[0][2]}")
    print(f"完整网格结果: {output}")
