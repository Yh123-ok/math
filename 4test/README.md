# 第四问：波动电价下重解第二问

先读 `reports/RESULTS_REPORT.md` 看数值，再读 `reports/METHOD.md` 看方法。提交结果为 `result4-2.xlsx`。本文件夹不计算第四问对应第三问的部分。

## 1. 信息边界

- 假设每天0:00可获得当天完整144段电价，明日电价不可见。这是本次用户指定的电价发布假设，并非附件本身证明的市场规则。
- 当天负载和光伏预测仅使用昨天及以前数据。日内控制仅观测当前段实际净负荷；后续段实际值不可见。
- 不使用附件3，不对锁定的正常购电量作日内调整。实时观测作为本段能量平衡的理想反馈，不等于提前知道整日实际值。
- 00:10是00:00–00:10的区间终点。结果副本纠正原模板偏移一格的时间表头，不平移输入数组，保留原模板原件。

## 2. 文件结构及用途

|文件|作用|
|---|---|
|`main.py`|统一入口：核验、预测、回测、因果测试、导出和验收|
|`config.py`|物理参数、预先固定的历史窗口和候选集|
|`src/data_io.py`|读取附件2、4和模板，统一单位和物理时间|
|`src/forecasting.py`|负载/光伏预测、历史组合权重及误差安全余量|
|`src/day_ahead.py`|当天正常购电计划，两阶段线性规划|
|`src/realtime.py`|即时放电及价格感知MPC，逐段执行且不改变正常计划|
|`src/backtest.py`|各候选连续运行；只按历史评分选择参数和控制器|
|`src/validation.py`|能量与库存约束校验、扰动未来数据的因果测试|
|`src/reporting.py`|CSV、Excel载荷、结果报告、独立重读验收和文件哈希|
|`src/figures.py`|从保存的CSV绘制中文矢量PDF|
|`tools/write_result.mjs`|用官方模板填写Excel并生成三页预览|
|`outputs/dispatch_all_year.csv`|全年正式策略逐十分钟的实际执行数据|
|`outputs/forecasts.csv`、`forecast_weights.csv`|当时生成的预测、净负荷误差和组合权重|
|`outputs/daily_summary.csv`、`summary.csv`|三种控制策略逐日与评价期合计|
|`outputs/selections.csv`、`risk_shadow_daily.csv`|每次选择的历史区间、各候选分数和原始日记录|
|`outputs/battery_four_hour.csv`、`emergency_events.csv`|全年四小时充放电、连续紧急购电事件|
|`outputs/time_mapping.csv`|原始时间、原模板标签和输出物理区间逐项映射|
|`outputs/checks.json`、`input_audit.json`、`manifest.json`|验收、输入核验、运行版本/配置/哈希|
|`reports/METHOD.md`|完整方法、公式、选型理由和局限|
|`reports/RESULTS_REPORT.md`|总结果、指定四日摘要和所有验收数值|
|`figures/*.pdf`|月费用、月紧急电量、6月21日调度、全年库存|

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

依赖：Python 3.10以上及 `requirements.txt` 中软件包；Excel作者工具需要Node.js与 `@oai/artifact-tool`。在已有Codex离线运行库时，程序自动定位Node和依赖，只在本目录创建依赖目录联接；普通环境需先确保该包可用。绘图需微软雅黑、黑体或Noto Sans CJK SC中文字体。

```powershell
python -m pip install -r 4test/requirements.txt
python 4test/main.py
```

入口按自身位置定位路径，从任意当前目录启动均可。若Node不在PATH，设置 `PROBLEM4_NODE` 为Node可执行文件路径。Excel依赖不可用时仍可独立复现全部数学计算、CSV和数值报告：

```powershell
python 4test/main.py --compute-only
```

`--export-only` 可从本机计算缓存再次生成文件；仅可读取自己生成的可信缓存。正常比赛复现使用默认命令，不需要缓存。浮点误差容限为1e-6 kWh；不同求解器版本遇到多解时细节可能不同，应先比对成本和约束。

## 4. 结果解释

评价期为2月1日至12月31日；1月用于历史积累，但仍按真实反馈逐日推进库存，不在2月重置。五倍紧急费用单独计入总费用。库存软目标是控制设计，非题面强制每日首末相等；该等式只属于第一问。

因果测试针对已实现代码的数据可见性；方案开发曾接触该题数据，故不将这些回测称为独立盲测。不得用年底结果倒选一条全年最便宜的策略作为正式结果。
