# 微网与外部电网电力调控策略：问题一

本仓库保存问题一的数据核验、双时间映射线性规划、完整调度结果、填写完成的结果表、中文矢量图和计算结果报告。当前仅完成问题一。

## 计算结果

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
