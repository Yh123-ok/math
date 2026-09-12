# 第四问重解第二问：正式版本

正式方案采用**简化负载预测＋固定80%历史误差安全余量＋价格感知MPC**。每天0:00锁定144段正常购电量，日内只根据当前真实供需执行储能与紧急购电。原光伏预测器、储能设备模型和电价假设保留。1月继续执行原负载预测，到2月1日只比较已结束的1月预测误差并冻结胜出的简单预测器；不倒改1月库存。所有输入均按“00:10是00:00—00:10的终点”处理；Excel保持官方模板的原表头、行列和列序。

2025年2—12月总费用 **14,293,469.31元**，紧急购电 **67,753.12 kWh**；相对旧联合方案节省 **287,022.93元（1.969%）**、紧急电量减少 **35,914.59 kWh**。费用含五倍紧急电费。未声称全年随机最优或独立盲测，已检查时间因果和物理约束。

|位置|用途|
|---|---|
|`main.py`|一条命令从原附件重新运行、填表、验收、绘图和写报告|
|`src/simple_load_forecast.py`|按过去日电量、低负载日类型和同类日形状预测负载|
|`src/forecasting.py`|原有因果光伏预测和历史误差分位数|
|`src/day_ahead.py`|日初购电LP及储能软终值|
|`src/realtime.py`|已知当日电价、冻结预测下的逐段MPC|
|`experiments/simple_mpc.py`|正式历史回测和逐段明细|
|`experiments/finalize_mpc.py`|按模板生成Excel，重读核对计划量、充放电量与紧急电量|
|`src/plot_mpc.py`|4组PDF/PNG绘图，仅读取已保存CSV|
|`notebooks/mpc_analysis.ipynb`|含完整绘图代码与已执行图像|
|`reports/METHOD.md`|公式、信息边界及全部解题步骤|
|`reports/RESULTS_REPORT.md`|费用、日期结果、预测与验收|
|`outputs/official_schedule.csv`|334天×144段完整实际调度|
|`outputs/official_daily.csv`、`official_summary.json`|每日及全年结算|
|`outputs/official_forecasts.csv`|预测与实际量，供误差图复核|
|`outputs/official_audit.json`、`official_causality.json`|Excel/物理/扰动验收|
|`result4-2.xlsx`|正式比赛提交结果|
|`archives/joint_v1/`|上一正式版的结果、方法和图表，供公平对照|

父目录必须包含 `附件/附件2.xlsx`、`附件/附件4.xlsx`、`附件/附件5/result4-2.xlsx`。输入单位kW转为每10分钟kWh。需 Python 3.10+、`requirements.txt` 内依赖，以及 Node.js 和 `@oai/artifact-tool` 用于填写Excel。若Node不在PATH，设置环境变量 `PROBLEM4_NODE`。

```powershell
python -m pip install -r 4test/requirements.txt
python 4test/main.py
```

入口按文件位置寻找附件，不依赖当前目录。图表单独重绘与逐字节核验：

```powershell
python 4test/tools/reproduce_mpc_notebook.py
```

不需要提前生成旧版影子候选。`experiments/` 中的其他脚本仅用于记录未采用的对照，不进入正式主程序。仓库不包含原始附件或本机依赖。
