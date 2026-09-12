import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "figures"
DISPATCH_NAME = "dispatch_problem4.csv"
PROBLEM = 4
T = 144
SLOTS_PER_HOUR = 6

FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
if Path(FONT_PATH).exists():
    plt.rcParams["font.family"] = font_manager.FontProperties(fname=FONT_PATH).get_name()
plt.rcParams["axes.unicode_minus"] = False


def configure(base_dir, problem):
    global HERE, OUTPUT, DISPATCH_NAME, PROBLEM
    HERE = Path(base_dir).resolve()
    OUTPUT = HERE / "figures"
    PROBLEM = int(problem)
    DISPATCH_NAME = f"dispatch_problem{problem}.csv"

def number(value):
    return 0.0 if value in (None, "") else float(value)

def read_dispatch():
    groups = defaultdict(list)
    with (HERE / DISPATCH_NAME).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["方案"] == "C":
                groups[date.fromisoformat(row["日期"])].append(row)
    if not groups or any(len(rows) != T for rows in groups.values()):
        raise ValueError(f"{DISPATCH_NAME} 缺少完整的 C 方案记录")
    return dict(sorted(groups.items()))

def arrays(rows):
    keys = ("电价", "实际负荷电量", "实际光伏电量", "原始计划购电量",
            "最终调整购电量", "增购量", "减购量", "调整交易价格",
            "紧急购电量", "充电量", "放电量", "弃电量", "SOC")
    return {key: np.array([number(row[key]) for row in rows]) for key in keys}

def daily_cost(values):
    return {
        "base": float(np.dot(values["电价"], values["原始计划购电量"])),
        "increase": float(np.dot(values["调整交易价格"], 1.5 * values["增购量"])),
        "refund": float(np.dot(values["调整交易价格"], 0.5 * values["减购量"])),
        "emergency": float(np.dot(values["电价"], 5 * values["紧急购电量"])),
    }

def month_axis(ax):
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

def decorate(ax, title, ylabel, xlabel=None, legend=False):
    """统一设置中文标题、坐标名和网格。"""
    ax.set(title=title, ylabel=ylabel, xlabel=xlabel)
    ax.grid(alpha=.25)
    if legend:
        ax.legend()

def save(fig, name):
    fig.savefig(OUTPUT / name, dpi=200, bbox_inches="tight")
    plt.close(fig)

def main(base_dir=None, problem=None):
    if base_dir is not None:
        configure(base_dir, problem)
    groups = read_dispatch()
    days = list(groups)
    data = {day: arrays(groups[day]) for day in days}
    costs = {day: daily_cost(data[day]) for day in days}
    emergency = np.array([data[day]["紧急购电量"].sum() for day in days])
    refund = np.array([data[day]["减购量"].sum() for day in days])
    if emergency.max() > 0 and refund.max() > 0:
        score = emergency / emergency.max() * refund / refund.max()
        chosen = days[int(np.argmax(score))]
    else:
        chosen = days[int(np.argmax(emergency))]
    values = data[chosen]
    hours = np.arange(T) / SLOTS_PER_HOUR
    OUTPUT.mkdir(exist_ok=True)

    # 计划、最终调整计划与全年正常购电费用。
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), constrained_layout=True)
    axes[0].plot(hours, values["原始计划购电量"], label="计划购电量", lw=1.6)
    axes[0].plot(hours, values["最终调整购电量"], label="调整购电量", lw=1.4)
    decorate(axes[0], f"{chosen:%Y年%m月%d日}计划购电与调整购电",
             "电量（kWh/10分钟）", "时刻", True)
    axes[0].set_xticks(np.arange(0, 25, 4))
    axes[1].plot(days, [costs[d]["base"] for d in days], label="原计划购电费")
    axes[1].plot(days, [costs[d]["base"] + costs[d]["increase"] - costs[d]["refund"]
                        for d in days], label="调整后正常购电费")
    decorate(axes[1], "全年每日正常购电费用", "费用（元/天）", "日期", True)
    month_axis(axes[1])
    save(fig, "购电计划与费用.png")

    # 同图展示计划、紧急购电、调整增购、减购退款。
    increase_cost = 1.5 * values["调整交易价格"] * values["增购量"]
    refund_cost = 0.5 * values["调整交易价格"] * values["减购量"]
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True, constrained_layout=True)
    axes[0].plot(hours, values["原始计划购电量"], label="计划购电量", lw=1.7)
    axes[0].plot(hours, values["最终调整购电量"], "--", label="调整购电量", lw=1.2)
    axes[0].bar(hours, values["紧急购电量"], width=1 / 6, alpha=.55, label="紧急购电量")
    axes[0].bar(hours, values["增购量"], width=1 / 6, alpha=.6, label="调整增购量")
    decorate(axes[0], f"{chosen:%Y年%m月%d日}购电构成", "电量（kWh/10分钟）")
    axes[0].set_xticks(np.arange(0, 25, 2))
    axes[0].legend(ncol=4)
    axes[1].bar(hours - 1 / 12, increase_cost, width=1 / 6, alpha=.65, label="调整增购费用")
    axes[1].bar(hours + 1 / 12, -refund_cost, width=1 / 6, alpha=.65,
                label="减购退款（负值表示返还）")
    axes[1].axhline(0, color="black", lw=.8)
    decorate(axes[1], "调整费用明细", "金额（元/10分钟）", "时刻")
    axes[1].legend(ncol=2)
    save(fig, "购电构成与调整费用.png")

    # 选定日储能运行。
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), constrained_layout=True)
    axes[0].bar(hours, values["充电量"], width=1 / 6, label="充电量")
    axes[0].bar(hours, -values["放电量"], width=1 / 6, label="放电量（负值）")
    axes[0].set_xticks(np.arange(0, 25, 4))
    decorate(axes[0], f"{chosen:%Y年%m月%d日}储能充放电",
             "电量（kWh/10分钟）", legend=True)
    soc_start = values["SOC"][0] + values["放电量"][0] / .9 - .9 * values["充电量"][0]
    soc_x = np.arange(T + 1) / SLOTS_PER_HOUR
    axes[1].plot(soc_x, np.r_[soc_start, values["SOC"]], marker=".", ms=2)
    axes[1].set_xticks(np.arange(0, 25, 4))
    decorate(axes[1], "储能状态", "储能量（kWh）", "时刻")
    save(fig, "储能运行.png")

    # 全年紧急购电量和费用。
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True, constrained_layout=True)
    axes[0].plot(days, emergency, color="#c44e52")
    decorate(axes[0], "全年每日紧急购电量", "电量（kWh/天）")
    axes[1].plot(days, [costs[d]["emergency"] for d in days], color="#dd8452")
    decorate(axes[1], "全年每日紧急购电费用", "费用（元/天）", "日期")
    month_axis(axes[1])
    save(fig, "紧急购电.png")
    print(f"图片已写入: {OUTPUT}；代表日期: {chosen}")

if __name__ == "__main__":
    main()
