# 问题二图表说明

本目录中的 PDF 均由 `src/figures.py` 从最终保存的 `outputs/daily_summary.csv` 重新读取并生成，不使用手工录入数据。

| 文件 | 内容 |
| --- | --- |
| `problem2_monthly_cost.pdf` | 2025年2月至12月正常计划购电费与五倍紧急购电费，采用堆叠柱形图 |
| `problem2_monthly_emergency.pdf` | 2025年2月至12月紧急购电量 |
| `problem2_soc.pdf` | 评价期逐日日末储电量及 1200、10800 kWh 运行边界 |

三张图均为单页矢量 PDF，使用中文坐标轴和图例。程序会检查页数、文件结构以及是否存在栅格图像对象；不合格时终止运行。
