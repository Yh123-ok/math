"""把内存结果转换为可审计的CSV、报告和Excel载荷。"""
from __future__ import annotations

import csv
from datetime import date
import json
from pathlib import Path
import numpy as np

import config as cfg


def write_csv(path: Path, rows):
    rows = list(rows)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def consolidate_emergency(values, threshold=1e-8):
    events, start, amount = [], None, 0.0
    for t, value in enumerate(values):
        if value > threshold:
            if start is None:
                start = t
            amount += float(value)
        elif start is not None:
            events.append((start, t, amount)); start, amount = None, 0.0
    if start is not None:
        events.append((start, len(values), amount))
    def clock(slot):
        minutes = slot*10
        return f"{minutes//60:02d}:{minutes%60:02d}"
    return [{"start_slot": a, "end_slot": b, "time_range": f"{clock(a)}-{clock(b)}", "kwh": value}
            for a, b, value in events]


def build_outputs(base, data, forecasts, results, selections, comparisons, checks):
    out = base / "outputs"; out.mkdir(parents=True, exist_ok=True)
    official_start = data.dates.index(date.fromisoformat(cfg.OFFICIAL_START))
    dispatch_rows = []
    forecast_rows = []
    daily_rows = []
    emergency_rows = []
    battery_rows = []
    for result in results:
        d = result.day; day = data.dates[d]
        q, actual = result.plan["q"], result.actual
        load_hat = forecasts["load_final"][d] if d else np.full(cfg.PERIODS, np.nan)
        pv_hat = forecasts["pv_final"][d] if d else np.full(cfg.PERIODS, np.nan)
        margin = np.zeros(cfg.PERIODS)
        if d and result.scheme == 2:
            from .forecasting import weighted_safety_margin
            margin = weighted_safety_margin(d, forecasts["net_error"], result.alpha)
        for t in range(cfg.PERIODS):
            dispatch_rows.append({
                "date": day.isoformat(), "period": data.interval_labels[t], "slot": t,
                "scheme": result.scheme, "alpha": result.alpha, "kappa": result.kappa,
                "price_yuan_per_kwh": data.prices[t], "load_kwh": data.load_kwh[d,t],
                "pv_kwh": data.pv_kwh[d,t], "plan_purchase_kwh": q[t],
                "charge_kwh": actual["charge"][t], "discharge_kwh": actual["discharge"][t],
                "emergency_kwh": actual["emergency"][t], "waste_kwh": actual["waste"][t],
                "soc_start_kwh": actual["soc"][t], "soc_end_kwh": actual["soc"][t+1],
            })
            if d:
                forecast_rows.append({
                    "date": day.isoformat(), "period": data.interval_labels[t], "slot": t,
                    "load_actual_kwh": data.load_kwh[d,t], "load_forecast_kwh": load_hat[t],
                    "pv_actual_kwh": data.pv_kwh[d,t], "pv_forecast_kwh": pv_hat[t],
                    "net_actual_kwh": data.load_kwh[d,t]-data.pv_kwh[d,t],
                    "net_forecast_kwh": load_hat[t]-pv_hat[t], "safety_margin_kwh": margin[t],
                    "net_error_kwh": forecasts["net_error"][d,t],
                })
        daily_rows.append({
            "date": day.isoformat(), "scheme": result.scheme, "alpha": result.alpha, "kappa": result.kappa,
            "initial_soc_kwh": result.initial_soc, "final_soc_kwh": actual["soc"][-1],
            "plan_purchase_kwh": float(q.sum()), "emergency_kwh": float(actual["emergency"].sum()),
            "charge_kwh": float(actual["charge"].sum()), "discharge_kwh": float(actual["discharge"].sum()),
            "waste_kwh": float(actual["waste"].sum()), "planned_cost_yuan": result.planned_cost,
            "emergency_cost_yuan": result.emergency_cost, "total_cost_yuan": result.total_cost,
        })
        if d >= official_start:
            for event in consolidate_emergency(actual["emergency"]):
                emergency_rows.append({"date": day.isoformat(), "time_range": event["time_range"],
                                       "emergency_kwh": event["kwh"]})
            for block in range(6):
                sl = slice(block*24, (block+1)*24)
                battery_rows.append({
                    "date": day.isoformat(), "time_range": f"{block*4:02d}:00-{(block+1)*4:02d}:00",
                    "charge_kwh": float(actual["charge"][sl].sum()),
                    "discharge_kwh": float(actual["discharge"][sl].sum()),
                    "time": "00:00" if block == 0 else ("24:00" if block == 1 else ""),
                    "soc_kwh": result.initial_soc if block == 0 else (float(actual["soc"][-1]) if block == 1 else ""),
                })
    write_csv(out / "dispatch_all_year.csv", dispatch_rows)
    write_csv(out / "forecasts_and_errors.csv", forecast_rows)
    write_csv(out / "daily_summary.csv", daily_rows)
    write_csv(out / "emergency_events.csv", emergency_rows if emergency_rows else [{"date":"","time_range":"","emergency_kwh":0}])
    write_csv(out / "four_hour_battery.csv", battery_rows)
    weight_rows = [{
        "date": data.dates[d].isoformat(), "load_weight_yesterday": forecasts["load_weight_a"][d],
        "load_weight_hierarchical": 1-forecasts["load_weight_a"][d] if np.isfinite(forecasts["load_weight_a"][d]) else "",
        "pv_weight_yesterday": forecasts["pv_weights"][d,0], "pv_weight_ewma": forecasts["pv_weights"][d,1],
        "pv_weight_shape_total": forecasts["pv_weights"][d,2],
    } for d in range(1, len(data.dates))]
    write_csv(out / "forecast_weights.csv", weight_rows)
    selection_rows, candidate_rows = [], []
    for s in selections:
        selection_rows.append({k:v for k,v in s.items() if k != "all_candidates"})
        for score, scheme, alpha, kappa, stage in s.get("all_candidates", []):
            candidate_rows.append({"effective_date":s["effective_date"], "stage":stage, "scheme":scheme,
                                   "alpha":alpha, "kappa":kappa, "inventory_adjusted_validation_cost_yuan":score})
    write_csv(out / "monthly_strategy_selection.csv", selection_rows)
    write_csv(out / "monthly_candidate_scores.csv", candidate_rows)
    write_csv(out / "scheme_comparison.csv", comparisons)
    mapping = [{"source_column": i+2, "source_timestamp": data.source_times[i],
                "physical_interval": data.interval_labels[i],
                "template_column_position": i+2} for i in range(cfg.PERIODS)]
    write_csv(out / "time_mapping.csv", mapping)

    official_results = results[official_start:]
    plan_values = []
    for result in official_results:
        plan_values.append([float(x) for x in result.plan["q"]] +
                           [float(result.plan["q"].sum()), float(result.total_cost)])
    excel_payload = {"plan_values": plan_values, "battery_rows": battery_rows,
                     "emergency_rows": emergency_rows, "output_path": str(base / "result2.xlsx")}
    (out / "excel_payload.json").write_text(json.dumps(excel_payload, ensure_ascii=False), encoding="utf-8")
    return daily_rows, emergency_rows, battery_rows


def make_report(base, data, daily_rows, selections, comparisons, checks, emergency_rows):
    official = [r for r in daily_rows if r["date"] >= cfg.OFFICIAL_START]
    total = lambda key: sum(float(r[key]) for r in official)
    specified = []
    for target in cfg.SPECIFIED_DATES:
        row = next(r for r in official if r["date"] == target)
        events = [e for e in emergency_rows if e["date"] == target]
        specified.append((target, row, events))
    lines = [
        "# 问题二计算结果报告", "",
        "本报告由 `run_problem2.py` 自动生成，只记录方案、参数、计算结果和校验。", "",
        "## 正式策略", "",
        "正式执行在每月第一天使用此前最多60天数据滚动选择方案。方案0为昨日同时间预测，方案1为分层预测，方案2为动态组合预测与时间衰减加权分位数。费用差不超过0.1%时选择更简单的方案。每天0:00确定正常购电，日内不调整该计划。", "",
        "实时阶段采用严格因果的单时段滚动优化。当前实际负载和光伏到达后，最小化该时段五倍紧急购电费；计划购电费已经发生，因此在实时目标中是常数。这个实现不使用未来实际值。", "",
        "## 主要结果（2025-02-01至2025-12-31）", "",
        "| 指标 | 数值 |", "| --- | ---: |",
        f"| 正常计划购电量 | {total('plan_purchase_kwh'):,.6f} kWh |",
        f"| 紧急购电量 | {total('emergency_kwh'):,.6f} kWh |",
        f"| 正常购电费 | {total('planned_cost_yuan'):,.6f} 元 |",
        f"| 五倍紧急购电费 | {total('emergency_cost_yuan'):,.6f} 元 |",
        f"| 实际总费用 | {total('total_cost_yuan'):,.6f} 元 |",
        f"| 评价期初储电量 | {official[0]['initial_soc_kwh']:,.6f} kWh |",
        f"| 评价期末储电量 | {official[-1]['final_soc_kwh']:,.6f} kWh |", "",
        "## 方案对照", "", "| 方案 | 说明 | 总费用/元 | 紧急购电量/kWh | 期末储电量/kWh |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    descriptions = {0:"昨日预测、无安全余量",1:"分层预测、无安全余量",2:"组合预测、80%加权分位数",9:"月度滚动选择的正式策略"}
    for row in comparisons:
        lines.append(f"| {row['scheme']} | {descriptions.get(row['scheme'],'')} | {row['total_cost_yuan']:,.6f} | {row['emergency_kwh']:,.6f} | {row['final_soc_kwh']:,.6f} |")
    lines += ["", "## 月度滚动选择", "", "| 生效日期 | 方案 | alpha | kappa | 验证起点 | 候选数 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for s in selections:
        lines.append(f"| {s['effective_date']} | {s['scheme']} | {s['alpha']} | {s['kappa']} | {data.dates[s['validation_start']]} | {s['candidates']} |")
    lines += ["", "## 四个指定日期", ""]
    for target, row, events in specified:
        lines += [f"### {target}", "", f"全天计划购电 {row['plan_purchase_kwh']:,.6f} kWh；全天总费用 {row['total_cost_yuan']:,.6f} 元；紧急购电 {row['emergency_kwh']:,.6f} kWh。", ""]
        if events:
            lines += ["| 紧急购电时段 | 电量/kWh |", "| --- | ---: |"]
            lines += [f"| {e['time_range']} | {e['emergency_kwh']:.6f} |" for e in events]
        else:
            lines.append("该日没有紧急购电。")
        lines.append("")
    lines += [
        "## 校验", "", "| 项目 | 数值 |", "| --- | ---: |",
        *[f"| {k} | {v} |" for k,v in checks.items() if isinstance(v,(int,float))], "",
        "正式计算的功率均先乘1/6小时转换为电量。每一天的初始储电量继承前一天实际末值；1月1日采用零计划购电冷启动。预测权重、误差分位数和月度参数选择只使用当时已经完成的历史日期。", "",
        "官方模板的计划表提供334天完整行；本结果还将充放电表扩展为334×6行，将紧急购电表扩展为所有连续紧急购电事件。模板原件没有修改。", "",
        "详细字段、模型公式和每个代码文件用途见 `METHOD.md` 与目录 `README.md`。", "",
    ]
    report_dir = base / "reports"; report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "RESULTS_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
