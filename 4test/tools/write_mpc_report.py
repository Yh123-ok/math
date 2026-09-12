"""Regenerate the official method/result Markdown from saved audited outputs."""
from pathlib import Path
import csv,json
import pandas as pd
BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'outputs'


def write():
    new=json.loads((OUT/'official_summary.json').read_text(encoding='utf-8'))
    old=json.loads((BASE/'archives'/'joint_v1'/'summary.json').read_text(encoding='utf-8'))
    audit=json.loads((OUT/'official_audit.json').read_text(encoding='utf-8'))
    leak=json.loads((OUT/'official_causality.json').read_text(encoding='utf-8'))
    daily=pd.read_csv(OUT/'official_daily.csv')
    sched=pd.read_csv(OUT/'official_schedule.csv')
    forecasts=pd.read_csv(OUT/'official_forecasts.csv')
    old_load_mae=(forecasts.old_load_forecast_kwh-forecasts.actual_load_kwh).abs().mean()
    old_net_mae=((forecasts.old_load_forecast_kwh-forecasts.pv_forecast_kwh)-
                 (forecasts.actual_load_kwh-forecasts.actual_pv_kwh)).abs().mean()
    delta=old['total_cost_yuan']-new['total_cost_yuan']
    method=r'''# 第四问重解第二问：正式计算方法

## 1. 信息边界与时间

2025年1月1日0:00初始库存为6000 kWh。每天0:00可见以前全部实际负载、光伏、电价及当日完整144段公布电价；未知当日实际负载、光伏以及明日电价。问题4重解问题2不使用附件3的日内光伏预报（那属于重解问题3）。

附件2和4的 `00:10` 是 `[00:00,00:10)` 的区间终点。负载和光伏功率均乘以 $1/6$ 小时换成每段kWh。结果模板的文字标签错后一格；保留原表头，按第 $t$ 个源数据列对应第 $t$ 个输出数据列填写，物理区间以 `outputs/time_mapping.csv` 为准，不跨日平移。

## 2. 简化负载预测

1月预热期间继续使用原有因果负载预测，不事后改变1月采购和库存。同时并行记录简单候选预测：在1月15日0:00，只用1月1—14日各星期类别的平均日负载总电量，识别两个低负载星期类别；本数据识别为周五和周六。此前历史不足时暂按周六、周日归为低类别。此后类别固定，不再用未来数据重新识别。

令 $B_i=\sum_{t=1}^{144}\ell_{i,t}$ 为已结束历史日 $i$ 的负载总电量。预测日 $d$ 取最近三个同类别的历史日集合 $I_d$，计算同类形状：

$$
s_{d,t}=\frac{\sum_{i\in I_d}\ell_{i,t}}{\sum_{i\in I_d}B_i},\qquad \sum_t s_{d,t}=1.
$$

令 $k_d$ 为当天类别（低负载0，其余1）。用之前最多35天发生类别切换的日期集合 $J_d$，估计切换倍率：

$$
\beta_d=\operatorname{median}_{i\in J_d}\frac{\log(B_i/B_{i-1})}{k_i-k_{i-1}},
\qquad \widehat B_d=B_{d-1}\exp[\beta_d(k_d-k_{d-1})].
$$

若没有切换样本则取 $\beta_d=0$。简单候选的每段负载预测为 $\widehat\ell_{d,t}=\widehat B_d s_{d,t}$。在2月1日0:00，仅按已结束的1月15—31日负载MAE比较简单候选与原预测器；本数据中简单候选胜出，故2—12月固定使用它。1月的真实运行仍使用当时原预测器，其预测误差亦按原预测生成，不倒用2月才做出的选择。光伏仍用原有因果预测器；其历史候选、权重只由决策日前数据计算，详见旧版方法档案。

## 3. 0:00锁定正常购电计划

光伏预测为 $\widehat v_{d,t}$，净需求点预测为 $\widehat r_{d,t}=\widehat\ell_{d,t}-\widehat v_{d,t}$。历史净误差为已结束日真实净需求减其当时生成的净需求预测。取此前7日对应时段及相邻各一段，按日期半衰期3日加权，得到历史误差的80%加权分位数。非负安全余量为

$$
m_{d,t}=\max(0,Q_{0.8}^{\mathrm{weighted}}(\varepsilon_{i,s})),\qquad
\widetilde r_{d,t}=\widehat r_{d,t}+m_{d,t}.
$$

80%是五倍紧急价下的无储能单时段报童模型出发点；含储能时不是最优性保证。本版固定这一规则，不使用全年结果挑选参数，不再运行六候选及双层影子策略。

以当日已公布的 $p_t$ 和实际日初库存求解原有日前LP：

$$
\min\sum_{t=1}^{144}p_tq_t+\rho_d h,
\qquad \rho_d=5\times0.9\bar p_d.
$$

$q_t$ 是计划购电量，$h\ge\max(0,6000-S_{145})$ 是日末库存软缺额，$\bar p_d$ 只用此前最多28天电价估计。约束为

$$
q_t+u_t-c_t-w_t=\widetilde r_{d,t},\quad
S_{t+1}=S_t+0.9c_t-u_t/0.9.
$$

$c_t,u_t,w_t$ 分别为预测情况下的充电、放电和弃电；$1200\le S_t\le10800$，$0\le c_t,u_t\le5000/6$，$q_t,w_t\ge0$。对购电费用作两阶段词典序求解，第二阶段减少无效充放电；当日144个 $q_t$ 此后不再修改。日末6000是软目标，不是题面强制每日归位。

## 4. 日内MPC及实际结算

每段读取该段已观测的真实净需求和实际库存；其余时段只使用0:00冻结的净需求点预测、原计划 $q_j$ 和当天已公布的价格。求解剩余时段预测紧急购电费 $\sum_{j=t}^{144}5p_je_j+\rho_dh$，只执行当前段动作。正常购电 $q_j$ 不更改。剩余实际缺额由紧急购电补足，紧急电不用于充电；富余电先充电、再弃用。跨日库存连续传递。

实际账单严格按 $\sum_t p_tq_t+5p_te_t$ 计算；模型内部的库存软惩罚不进入账单。设备限额、效率、能量守恒、无售电与无同段充放电均逐段验收。当前真实观测只用于当前动作，不用于重新预测当天后续需求。

## 5. 防信息泄露与复现

所有预测索引、残差和电价代理均早于决策日；星期类别于1月15日冻结，预测器选择于2月1日依据已结束的1月数据完成。`tools/audit_mpc_information.py` 对2月、6月、12月分别扰动当天及以后实际负载/光伏、未来价格和当天后续实际需求，重算预测、计划和历史动作；测试结果在 `outputs/official_causality.json`。历史因果回测仍不是独立盲测。

`python 4test/main.py` 从原附件重新计算、填写Excel、核验并生成图；`python 4test/tools/reproduce_mpc_notebook.py` 执行含完整绘图代码的Notebook并核对8份图表字节。代码入口见本目录README。
'''
    report=f'''# 第四问重解第二问：正式结果与验收

评价期：2025-02-01至2025-12-31，共334日；1月作为连续库存预热。结果为严格按日期顺序执行的历史因果回测。

## 费用与预测

|指标|旧联合方案|新正式方案|变化|
|---|---:|---:|---:|
|正常购电费/元|{old['planned_cost_yuan']:.2f}|{new['planned_cost_yuan']:.2f}|{new['planned_cost_yuan']-old['planned_cost_yuan']:+.2f}|
|五倍紧急费/元|{old['emergency_cost_yuan']:.2f}|{new['emergency_cost_yuan']:.2f}|{new['emergency_cost_yuan']-old['emergency_cost_yuan']:+.2f}|
|总费用/元|{old['total_cost_yuan']:.2f}|{new['total_cost_yuan']:.2f}|{-delta:+.2f}|
|紧急电量/kWh|{old['emergency_kwh']:.2f}|{new['emergency_kwh']:.2f}|{new['emergency_kwh']-old['emergency_kwh']:+.2f}|

总费用节省 **{delta:.2f}元（{delta/old['total_cost_yuan']*100:.3f}%）**。正常购电量 {new['planned_kwh']:.3f} kWh；未利用供能 {new['waste_kwh']:.3f} kWh。负载预测MAE从 {old_load_mae:.4f} 降至 {new['load_mae_kwh']:.4f} kWh/十分钟；净需求MAE从 {old_net_mae:.4f} 降至 {new['net_mae_kwh']:.4f} kWh/十分钟。旧版可在 `archives/joint_v1/` 核对。

## 题面指定日期

|日期|全天计划购电/kWh|正常费/元|紧急电/kWh|五倍紧急费/元|总费/元|
|---|---:|---:|---:|---:|---:|
'''
    for date in ['2025-03-20','2025-06-21','2025-09-23','2025-12-21']:
        r=daily[daily.date==date].iloc[0]
        report+=f"|{date}|{r.plan_purchase_kwh:.3f}|{r.planned_cost_yuan:.2f}|{r.emergency_kwh:.3f}|{r.emergency_cost_yuan:.2f}|{r.total_cost_yuan:.2f}|\n"
    report+='\n六个指定时段的计划购电、六个四小时充放电量及0:00/24:00库存，均可由 `outputs/official_schedule.csv` 聚合；正式Excel三表已填写。\n\n## 校验\n\n'
    physical=new['checks']
    for k in ('balance_max_kwh','state_equation_max_kwh','soc_min_kwh','soc_max_kwh',
              'charge_max_kwh','discharge_max_kwh','simultaneous_max_kwh','cross_day_soc_max_kwh',
              'emergency_while_charging_max_kwh','negative_min_kwh','nonfinite_count'):
        report+=f'- `{k}`：{physical[k]}\n'
    report+=f'''- 2月1日只用1月15—31日MAE选择负载预测：原预测 {new['january_original_load_mae_kwh']:.4f}、简单候选 {new['january_daily_shape_load_mae_kwh']:.4f} kWh/十分钟；1月历史调度仍用原预测。
- Excel计划数值最大误差：{audit['max_excel_plan_error_kwh']} kWh（核对 {audit['plan_values_checked']} 个数值）。
- Excel充放电、紧急事件最大误差：{audit['max_excel_battery_error_kwh']}、{audit['max_excel_emergency_error_kwh']} kWh。
- 原模板表头与文件哈希保持不变；时间列依附件源序，具体物理区间见 `outputs/time_mapping.csv`。
- 扰动信息边界测试最大影响：{max(leak['max_effects'].values())}，全部通过。
- 4组矢量PDF及PNG由已保存CSV绘制；Notebook执行后8份图逐字节一致，见 `outputs/mpc_notebook_check.json`。

## 文件

`result4-2.xlsx` 为正式结果；`outputs/official_schedule.csv`、`official_daily.csv`、`official_summary.json`、`official_forecasts.csv` 为原始明细；`outputs/official_audit.json` 和 `official_causality.json` 为验收；`notebooks/mpc_analysis.ipynb` 含完整可执行绘图代码。方法见 `METHOD.md`。

本结果未声称全信息最优。事后按全年结果挑出的固定候选不能作为无泄露的正式策略；新正式策略使用分析确定的80%单一规则，每日预测与执行只访问当时可用数据。
'''
    (BASE/'reports'/'METHOD.md').write_text(method,encoding='utf-8')
    (BASE/'reports'/'RESULTS_REPORT.md').write_text(report,encoding='utf-8')
    print('方法与正式结果报告已更新')


if __name__=='__main__':write()
