# 问题三代码

环境：Python 3.10 及以上。先安装依赖：

```bash
pip install -r requirements.txt
```

输入文件放在本目录的 `附件/` 下：`附件1.xlsx`、`附件2.xlsx`、
`附件3.xlsx` 和 `附件5/result3.xlsx`。

```bash
# 核心算法：生成正式 C 方案 result3.xlsx
python problem3.py

# 同时生成 A/B/C 对比汇总 scheme_summary.csv
python problem3.py --compare

# 用 1 月 8—31 日运行有限网格校准
python calibrate_problem3.py

# 按官方结果表字段生成中文图片
python plot_problem3.py
```

正式冻结参数为 `beta=0.5`、`terminal_target=4800 kWh`、
`rho_multiplier=1.0`。校准脚本会写出 `calibration.csv` 和
`frozen_parameters.json`，核心程序会优先读取冻结文件。校准指标为实际费用减去期末电量折价残值，正式费用不扣残值。

文件分工：`problem3.py` 是问题三入口；实际算法复用上级目录的
`dispatch_core.py`，校准和绘图也分别复用 `calibrate_common.py`、`plot_common.py`。
`calibrate_problem3.py` 是参数网格搜索，`plot_problem3.py` 是中文绘图。图片输出到 `figures/`，包括计划购电、调整增购、
减购退款、紧急购电和储能运行图：`购电计划与费用.png`、
`购电构成与调整费用.png`、`储能运行.png`、`紧急购电.png`。
