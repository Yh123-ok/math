# C题：问题三与问题四-3整合提交

本仓库包含问题三和问题四条件下重算问题三的可复现代码、正式结果、逐时账本、图片和模型说明。两个问题共享日前计划、滚动调整、储能仿真、校准与绘图代码，分别保留独立入口、参数和结果。

两题均采用在2025年1月15日冻结类别的“类别切换 + 形状×总量”因果负荷预测。光伏使用附件3在00:00、06:00、12:00和18:00发布的预报；问题三使用附件1固定日内电价，问题四-3使用附件4逐日电价。

## 正式结果

评价期为2025年2月1日至12月31日，共334天。正式提交采用完整使用四个光伏预报时刻的C方案。

| 问题 | 正式总费用（元） | 紧急购电量（kWh） | 期末SOC（kWh） | 冻结参数 $(\beta,S^\star,\rho/\bar p)$ |
| --- | ---: | ---: | ---: | --- |
| [问题三](problem3/问题3模型说明.md) | 13,152,569.49 | 36,369.21 | 4,694.66 | $(0.6,4800,2.0)$ |
| [问题四-3](problem4-3/问题4-3模型说明.md) | 13,761,589.53 | 40,032.79 | 5,930.46 | $(0.6,6000,1.0)$ |

完整费用构成、受控预测器对照、信息边界和结算假设见各问题的模型说明。

## 目录

```text
整合提交/
├── dispatch_core.py          # 共享调度与结果写出
├── calibrate_common.py       # 共享1月参数校准
├── plot_common.py            # 共享中文绘图
├── problem3/
│   ├── problem3.py           # 问题三入口
│   ├── 问题3模型说明.md
│   ├── result3.xlsx
│   ├── dispatch_problem3.csv
│   ├── scheme_summary.csv
│   ├── figures/
│   └── 附件/
└── problem4-3/
    ├── problem4.py           # 问题四-3入口
    ├── 问题4-3模型说明.md
    ├── result4-3.xlsx
    ├── dispatch_problem4.csv
    ├── scheme_summary.csv
    ├── figures/
    └── 附件/
```

各问题目录中的 `frozen_parameters.json` 是正式参数，`calibration.csv` 是1月网格校准记录，`problem*_config.json` 记录模型参数和候选网格。`附件/附件5/` 保存官方空白模板，目录根部的 `result*.xlsx` 是已填写的正式结果。

## 复现

Python 3.10及以上。在任一问题目录安装依赖后运行：

```bash
cd problem3
pip install -r requirements.txt
python calibrate_problem3.py
python problem3.py --compare
python plot_problem3.py
```

```bash
cd problem4-3
pip install -r requirements.txt
python calibrate_problem4.py
python problem4.py --compare
python plot_problem4.py
```

校准只使用1月8日至31日。正式计算从1月1日6000 kWh开始连续传递SOC，并输出完整334天结果。`--compare` 会生成只用00:00预报的A方案、增加12:00预报的B方案和使用全部四次预报的C方案；正式Excel写入C方案。

## 结果入口

| 内容 | 问题三 | 问题四-3 |
| --- | --- | --- |
| 运行说明 | [README](problem3/README.md) | [README](problem4-3/README.md) |
| 模型说明 | [问题3模型说明](problem3/问题3模型说明.md) | [问题4-3模型说明](problem4-3/问题4-3模型说明.md) |
| 正式Excel | [result3.xlsx](problem3/result3.xlsx) | [result4-3.xlsx](problem4-3/result4-3.xlsx) |
| A/B/C汇总 | [scheme_summary.csv](problem3/scheme_summary.csv) | [scheme_summary.csv](problem4-3/scheme_summary.csv) |
| 逐时账本 | [dispatch_problem3.csv](problem3/dispatch_problem3.csv) | [dispatch_problem4.csv](problem4-3/dispatch_problem4.csv) |
| 结果图片 | [figures](problem3/figures/) | [figures](problem4-3/figures/) |

当前结算按最终调整计划相对00:00原计划的净偏差计算，并使用最后一次生效调整的交易时刻价格。问题四-3的终端惩罚和校准残值使用附件4全年平均电价；这些口径未因本次目录整理而改变。
