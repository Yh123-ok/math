# 第四问：波动电价下重解第二问

先读 `reports/OPTIMIZATION_ANALYSIS.md` 看新旧比较，再读 `reports/RESULTS_REPORT.md` 和 `reports/METHOD.md`。正式方案为同起点12组合联合选择，提交结果为 `result4-2.xlsx`。图表复现入口为 `notebooks/analysis_plots.ipynb`。本文件夹不计算第四问对应第三问的部分。

## 1. 信息边界

- 假设每天0:00可获得当天完整144段电价，明日电价不可见。这是本次用户指定的电价发布假设，并非附件本身证明的市场规则。
- 当天负载和光伏预测仅使用昨天及以前数据。日内控制仅观测当前段实际净负荷；后续段实际值不可见。
- 不使用附件3，不对锁定的正常购电量作日内调整。实时观测作为本段能量平衡的理想反馈，不等于提前知道整日实际值。
- 00:10是00:00–00:10的区间终点。按用户要求保留原模板全部表头，按原始数据列序填写结果，不平移数组；模板文字与物理区间的差异在 `outputs/time_mapping.csv` 明确列出。

## 2. 文件结构及用途

|文件|作用|
|---|---|
|`main.py`|统一入口：核验、预测、回测、因果测试、导出和验收|
|`config.py`|物理参数、预先固定的历史窗口和候选集|
|`src/data_io.py`|读取附件2、4和模板，统一单位和物理时间|
|`src/forecasting.py`|负载/光伏预测、历史组合权重及误差安全余量|
|`src/day_ahead.py`|当天正常购电计划，两阶段线性规划|
|`src/realtime.py`|即时放电及价格感知MPC，逐段执行且不改变正常计划|
|`src/backtest.py`|原分层策略基准及通用历史评分|
|`src/joint_search.py`|12组合连续联合、同库存起点历史重放、正式逐日执行|
|`src/validation.py`|能量与库存约束校验、扰动未来数据的因果测试|
|`src/reporting.py`|CSV、Excel载荷、结果报告、独立重读验收和文件哈希|
|`src/analysis.py`|从CSV生成比较表、候选统计及分析报告，不参与决策|
|`src/plot_analysis.py`|10张Matplotlib图的完整源码，中文矢量PDF与PNG|
|`notebooks/analysis_plots.ipynb`|包含完整绘图源码和实际执行输出的Notebook|
|`tools/build_notebook.py`|由绘图源码生成Notebook，保持两者同步|
|`tools/reproduce_notebook.py`|执行Notebook并核对20个图文件逐字节一致|
|`tools/check_memoization.py`|比较重叠历史窗口有无缓存的12组合评分是否相同|
|`tools/write_result.mjs`|用官方模板填写Excel并生成三页预览|
|`outputs/dispatch_all_year.csv`|全年正式策略逐十分钟的实际执行数据|
|`outputs/forecasts.csv`、`forecast_weights.csv`|当时生成的预测、净负荷误差和组合权重|
|`outputs/daily_summary.csv`、`summary.csv`|五种对照/正式策略逐日与评价期合计|
|`outputs/selections.csv`、`risk_shadow_daily.csv`|每次选择的历史区间、各候选分数和原始日记录|
|`outputs/selection_scores.csv`|两种联合规则每次12候选评分与初末库存|
|`outputs/strategy_comparison.csv`、`monthly_comparison.csv`|费用节省、紧急量变化及单价的总体和月度对照|
|`outputs/candidate_comparison.csv`、`selection_frequency.csv`|固定组合事后诊断和历史选中次数|
|`archives/layered_v1/`|此次改进前的结果与汇总快照|
|`outputs/battery_four_hour.csv`、`emergency_events.csv`|全年四小时充放电、连续紧急购电事件|
|`outputs/time_mapping.csv`|源数据列、输出列、原样保留的模板标签与实际物理区间逐项映射|
|`outputs/checks.json`、`input_audit.json`、`manifest.json`|验收、输入核验、运行版本/配置/哈希|
|`reports/METHOD.md`|完整方法、公式、选型理由和局限|
|`reports/INFORMATION_BOUNDARY.md`|逐环节信息边界、历史重放为何允许及泄露测试说明|
|`reports/RESULTS_REPORT.md`|总结果、指定四日摘要和所有验收数值|
|`figures/*.pdf`、`*.png`|10组费用、紧急电量、评分、选择、参数交互和调度分析图|

## 3. 一条命令复现

将本文件夹放在题目目录下，父目录包含：

```text
附件/
  附件2.xlsx
  附件4.xlsx
  附件5/result4-2.xlsx
4test/
  main.py
```

依赖：Python 3.10以上及 `requirements.txt` 中软件包；Excel作者工具需要Node.js与 `@oai/artifact-tool`。在已有Codex离线运行库时，程序自动定位Node和依赖，只在本目录创建依赖目录联接；普通环境需先确保该包可用。绘图默认微软雅黑或黑体，其他系统用 `PROBLEM4_FONT` 指定中文TrueType字体。

```powershell
python -m pip install -r 4test/requirements.txt
python 4test/main.py
```

入口按自身位置定位路径，从任意当前目录启动均可。若Node不在PATH，设置 `PROBLEM4_NODE` 为Node可执行文件路径。Excel依赖不可用时仍可独立复现全部数学计算、CSV和数值报告：

```powershell
python 4test/main.py --compute-only
```

`--export-only` 可从本机计算缓存再次生成文件；仅可读取自己生成的可信缓存。正常比赛复现使用默认命令，不需要缓存。浮点误差容限为1e-6 kWh；不同求解器版本遇到多解时细节可能不同，应先比对成本和约束。

仅复现图表：在Jupyter或VS Code中打开Notebook，选择安装上述依赖的Python内核，点击“全部运行”。无需读取原始附件或重新求解。自动执行与一致性验收：

```powershell
python 4test/tools/reproduce_notebook.py
```

正式图仍在figures目录；验收副本在outputs/notebook_reproduction，检查结果在outputs/notebook_reproduction.json。单次生成10个PDF和10个PNG；同环境与同字体下应逐字节一致，跨环境以视觉和数值一致为准。Notebook展示全部绘图代码与图像，不只是调用一个隐藏函数。

## 4. 结果解释

评价期为2月1日至12月31日；1月用于历史积累，但仍按真实反馈逐日推进库存，不在2月重置。五倍紧急费用单独计入总费用。库存软目标是控制设计，非题面强制每日首末相等；该等式只属于第一问。

因果测试针对已实现代码的数据可见性；方案开发曾接触该题数据，故不将这些回测称为独立盲测。不得用年底结果倒选一条全年最便宜的策略作为正式结果。
