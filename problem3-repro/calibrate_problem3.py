#用 1 月 8—31 日历史回放选择问题三参数。
import csv
import json
from pathlib import Path
import problem3 as p3

def main():
    # 先生成历史预测和安全裕度；校准期只使用 1 月 8—31 日。
    dates, price, cold_load, pv_power, load, pv, forecast_map = p3.read_inputs()
    load_hat = p3.build_load_forecast(dates, load, cold_load)
    pv_hat = p3.build_pv_forecast(dates, pv_power, forecast_map)
    startup_margins = p3.build_safety_margins(
        dates, load, pv, load_hat, pv_hat, p3.STARTUP_BETA
    )
    average_price = float(price.mean())
    warmup = p3.simulate_range(
        p3.Scheduler(price), range(p3.WARMUP_END_INDEX), dates, load, pv,
        load_hat, pv_hat, startup_margins, p3.INITIAL_SOC,
        p3.LPParameters(p3.STARTUP_TARGET, p3.STARTUP_RHO_MULTIPLIER * average_price),
    )
    config = json.loads(Path(__file__).with_name("problem3_config.json").read_text("utf-8"))
    rows = []
    # 逐一尝试安全裕度分位数、期末 SOC 目标和终端惩罚系数。
    for beta in config["safety_quantile_grid"]:
        margins = p3.build_safety_margins(dates, load, pv, load_hat, pv_hat, beta)
        for target in config["terminal_target_grid_kwh"]:
            for multiplier in config["rho_multiplier_grid"]:
                params = p3.LPParameters(float(target), float(multiplier) * average_price)
                results = p3.simulate_range(
                    p3.Scheduler(price), range(p3.WARMUP_END_INDEX, p3.EVALUATION_START_INDEX),
                    dates, load, pv, load_hat, pv_hat, margins, warmup[-1].s_end, params,
                )
                cost = sum(p3.settlement(result, price) for result in results)
                # 用期末储能残值修正评分，避免只追求短期购电费。
                score = cost - config["salvage_rate_multiplier"] * average_price * results[-1].s_end
                rows.append([beta, target, multiplier, cost, results[-1].s_end, score])

    rows.sort(key=lambda row: row[-1])  # 评分越小越好
    output = Path(__file__).with_name("calibration.csv")
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
    Path(__file__).with_name("frozen_parameters.json").write_text(
        json.dumps(frozen, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"最优参数: beta={rows[0][0]}, terminal_target={rows[0][1]}, rho_multiplier={rows[0][2]}")
    print(f"完整网格结果: {output}")

if __name__ == "__main__":
    main()
