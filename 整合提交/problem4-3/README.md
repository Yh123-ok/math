# 问题四条件下问题三

完整数学模型、冻结参数、费用公式和结果图片见 [问题4-3模型说明](问题4-3模型说明.md)。

本目录只重新求解问题四条件下的第三问。附件 4 已在每天 00:00 给出当天完整的 144 个十分钟电价，因此不做价格预测；负荷使用 1 月 15 日冻结类别的“类别切换 + 形状×总量”预测，附件 3 光伏滚动预报、储能回放和 A/B/C 方案保持原有规则。

## 文件

- `problem4.py`：问题四-3入口，生成正式 C 方案 `result4-3.xlsx`、逐时账本和（可选）A/B/C 汇总。
- 上级目录的 `dispatch_core.py`、`calibrate_common.py`、`plot_common.py` 提供共享算法、校准和绘图实现。
- `calibrate_problem4.py`：安全裕度分位数、末端 SOC 目标和惩罚系数的网格搜索。
- `plot_problem4.py`：读取逐时账本，生成中文图片。
- `problem4_config.json`：模型参数和网格候选值。
- `附件/`：输入数据和官方 `result4-3.xlsx` 模板。

## 运行

```bash
pip install -r requirements.txt
python calibrate_problem4.py       # 可选：重新校准并写 frozen_parameters.json
python problem4.py --compare       # 完整 334 天，输出 C 结果和 A/B/C 对比
python plot_problem4.py            # 生成 figures/ 下的中文图
```

调试时可用 `python problem4.py --smoke-days 1 --compare` 只运行评价期第一天。

## 结算口径

- 日前原计划和紧急购电按当天对应交付时段的附件 4 电价结算。
- 增购、减购按发生该次滚动调整的交易时刻电价结算；减购净变化为 `-0.5 * 价格 * 减购量`。
- 每个交付时段相对 00:00 原计划只结算最终净偏差一次，不能累加多轮 LP 目标值。

正式评价期为 2025-02-01 至 2025-12-31（334 天）；1 月只用于预热和参数校准。
正式冻结参数为 `beta=0.6`、`terminal_target=6000 kWh`、`rho_multiplier=1.0`。
