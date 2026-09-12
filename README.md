# 微网与外部电网电力调控策略

本仓库目前包含问题一、问题二，以及第四问重解第二问的可复现代码、计算结果、结果表、方法说明与验收记录。

## 第四问重解第二问（4test）

- [文件结构与复现入口](4test/README.md)、[完整方法](4test/reports/METHOD.md)、[结果与验收](4test/reports/RESULTS_REPORT.md)。
- [正式结果 result4-2.xlsx](4test/result4-2.xlsx)、[运行入口 main.py](4test/main.py)、[CSV明细](4test/outputs/)、[10组PDF和PNG](4test/figures/)。
- [优化对比分析](4test/reports/OPTIMIZATION_ANALYSIS.md)、[可执行绘图Notebook（含完整绘图代码）](4test/notebooks/analysis_plots.ipynb)、[信息边界与防泄露验收](4test/reports/INFORMATION_BOUNDARY.md)。Notebook已实际执行，20个重绘PDF/PNG与正式图逐字节一致。
- 假设每天0:00已知当天完整电价；负载、光伏预测及策略选择只使用历史信息，不使用明日电价。附件时间按区间终点处理；Excel保留原模板表头，按源数据列序填写，文字偏移及实际物理区间另有逐列映射说明。
- 2025年2—12月正式总费用 **14,580,492.239221元**，紧急购电 **103,667.711485 kWh**。比原分层策略节省 **9,602.678122元（0.0658%）**，紧急购电减少 **804.999493 kWh**。
- 六组风险参数与G/MPC控制器组成12个联合候选，只按决策日前的历史评分选择。正式采用同起点历史重放；本数据中与连续联合策略43次选择均相同，没有额外重放收益。旧分层结果保存在 `4test/archives/layered_v1/`，供核对。
- 本次新增内容集中于 `4test/`；第一问和第二问求解程序未因此改动。此目录不含第四问对应第三问的结果。

## 推荐阅读入口

| 内容 | 第一问 | 第二问 |
| --- | --- | --- |
| 完整目录 | [`C题/`](C题/) | [`2test/`](2test/) |
| 一键运行入口 | [`C题/code/problem1.py`](C题/code/problem1.py) | [`2test/run_problem2.py`](2test/run_problem2.py) |
| 正式 Excel | [`C题/result1.xlsx`](C题/result1.xlsx) | [`2test/result2.xlsx`](2test/result2.xlsx) |
| 核心结果报告 | [`C题/reports/RESULTS_REPORT.md`](C题/reports/RESULTS_REPORT.md) | [`2test/reports/RESULTS_REPORT.md`](2test/reports/RESULTS_REPORT.md) |
| 方法与约束 | [`C题/建模方案.md`](C题/建模方案.md) | [`2test/reports/METHOD.md`](2test/reports/METHOD.md) |
| 约束验收 | [`C题/code/outputs/problem1_validation.json`](C题/code/outputs/problem1_validation.json) | [`2test/reports/CONSTRAINT_AUDIT.md`](2test/reports/CONSTRAINT_AUDIT.md) |
| 防信息泄露 | 不涉及滚动预测 | [`2test/reports/LEAKAGE_AUDIT.md`](2test/reports/LEAKAGE_AUDIT.md) |
| 完整数值明细 | [`C题/code/outputs/`](C题/code/outputs/) | [`2test/outputs/`](2test/outputs/) |
| 图表 | [`C题/figures/`](C题/figures/) | [`2test/figures/`](2test/figures/) |

根目录中的 `code/`、`figures/`、`reports/` 和 `result1.xlsx` 是第一问早期上传时保留的兼容副本。阅读和复现第一问时，以结构完整的 `C题/` 为准；第二问所有正式内容都在 `2test/`，最新第二问提交没有修改第一问。

## 第一问计算结果

正式结果采用口径 B（源数据时间是区间起点），并明确使用典型日的 24 小时周期映射处理模板末尾跨日时段。口径 A（源数据时间是区间终点）作为敏感性结果完整保留。详细映射和初始储电量解释见[结果报告](reports/RESULTS_REPORT.md)。

| 指标 | 数值 |
| --- | ---: |
| 第一阶段最优购电费 | 35,126.848589 元 |
| 正式调度购电费（第二阶段） | 35,126.848941 元 |
| 全天购电量 | 59,482.698167 kWh |
| 无储能基线费用 | 48,052.046591 元 |
| 节省费用 | 12,925.197650 元 |
| 节省比例 | 26.898329% |
| 00:00 / 24:00 储电量 | 6,000 / 6,000 kWh |
| 能量平衡最大绝对残差 | 1.14 × 10⁻¹³ kWh |

采用 `scipy.optimize.linprog(method="highs")` 进行两阶段词典序优化：先最小化购电费用，再在规定的费用容差内最小化充放电总量。两种口径均成功求解，未触发 MILP 回退，无同时充放电。

## 文件入口

- [结果报告](reports/RESULTS_REPORT.md)：输入核验、时间映射、六个指定时段和六个四小时区间摘要、基线比较及验收结果。
- [正式结果 result1.xlsx](result1.xlsx)：从官方模板复制，只填写 158 个结果单元格，保留原标签、结构与格式。
- [求解入口](code/problem1.py)与[表格辅助程序](code/fill_template.mjs)。
- [正式调度 CSV](code/outputs/problem1_schedule.csv)、[汇总 CSV](code/outputs/problem1_summary.csv)。
- [口径比较](code/outputs/problem1_mapping_comparison.csv)、[逐行时间映射](code/outputs/problem1_time_mapping.csv)。
- [调度图](figures/problem1_dispatch.pdf)、[储电量图](figures/problem1_soc.pdf)、[费用对比图](figures/problem1_cost_comparison.pdf)：中文矢量 PDF。
- `code/outputs/`：完整数值与核验 JSON，以 `problem1_validation.json` 为输出验收记录。
- `code/qa/`：模板与图表的可视化验收图。

仓库仅发布生成的成果。原题 PDF、建模方案、输入附件、官方空白模板、运行日志及本机依赖未上传。

## 复现

入口使用脚本所在位置确定项目根目录，不依赖当前启动目录。

复现前，请在仓库目录中放置你持有的以下四份原始文件，代码会先核验它们：

```text
建模方案.md
C题.pdf
附件/附件1.xlsx
附件/附件5/result1.xlsx
```

其中附件 1 是唯一数值输入，附件 5 中的文件为官方空白模板，不能用根目录中已填写的 `result1.xlsx` 替代。

```powershell
python "<仓库目录>\code\problem1.py"
```

依赖见 `code/requirements.txt`。表格填写与渲染还需要 Node.js 和 `@oai/artifact-tool`，这部分并非仅安装 Python 依赖即可使用。已验证环境是 Windows 上的 Codex 捆绑运行时，程序默认在用户目录中自动定位该运行时，并建立 `code/node_modules` 目录联接。运行时依赖和目录联接不随结果上传。

本机 Codex 环境示例：

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" "<仓库目录>\code\problem1.py"
```

使用其他环境时，需要先提供对应依赖，并可通过环境变量指定：

- `PROBLEM1_NODE`：Node.js 可执行文件。
- `PROBLEM1_CHINESE_FONT`：中文 TrueType 字体文件，默认 `C:/Windows/Fonts/simhei.ttf`。

`code/node_modules/@oai/artifact-tool` 需能被表格辅助程序解析。代码不会修改全局 Python 环境。

程序先记录输入核验，再计算两个口径、保存结果、填写模板、生成图表，并重新读取 CSV、Excel、PDF 验收。失败时保留运行日志并返回非零退出码。
