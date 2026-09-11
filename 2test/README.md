# 问题二可复现求解程序

本目录独立完成问题二的数据核验、因果预测、滚动参数选择、日前购电优化、实时储能执行、费用结算、结果校验和官方模板填写。

## 一条命令运行

在项目根目录或任意其他目录执行：

```powershell
python D:\shumo_n\C_newprompt\2test\run_problem2.py
```

程序通过入口文件的位置查找项目根目录，不依赖启动目录。输入文件保持在项目根目录的 `附件` 中。

## 代码结构

```text
2test/
├─ run_problem2.py          唯一运行入口，串联全部步骤
├─ config.py                电池参数、预测窗口和参数网格
├─ requirements.txt         Python依赖
├─ src/
│  ├─ data_io.py            输入读取、单位转换、时间与模板核验
│  ├─ forecasting.py        负载和光伏候选预测、因果组合权重
│  ├─ optimization.py       日前线性规划与实时滚动储能控制
│  ├─ simulation.py         多方案回放、月度参数选择、全年执行
│  ├─ validation.py         物理约束、信息边界、费用和文件校验
│  ├─ reporting.py          CSV与Markdown报告整理
│  └─ figures.py            从已保存结果绘制并校验矢量PDF图
├─ tools/
│  └─ write_result2.mjs     基于官方模板生成Excel结果
├─ outputs/                 运行生成的明细、汇总、权重和校验结果
├─ reports/                 运行生成的结果报告
└─ figures/                 运行生成的矢量PDF图
```

完整变量定义、预测权重、滚动验证、优化目标和约束见 `reports/METHOD.md`。

## 信息边界

日期 `d` 的预测和计划只读取日期 `< d` 的实际值及历史预测误差。当天实际负载和光伏只在对应十分钟时段到达后用于执行。2月1日储电量由1月运行过程继承，程序不重置电池。

官方模板时间标签与附件列标签存在一格歧义。物理计算采用附件时间为区间终点的口径；模板写入按其既定144列顺序保存，并在 `outputs/time_mapping.csv` 和结果报告中明确记录这一差异。
