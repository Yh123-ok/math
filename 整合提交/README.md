# C题整合提交

本目录将问题三和问题四-3整理为两个独立入口，共享同一套调度、校准和绘图实现。

## 目录

- `dispatch_core.py`：共享日前计划、滚动调整、储能仿真、校验和结果写出。
- `calibrate_common.py`：共享参数校准。
- `plot_common.py`：共享中文绘图。
- `problem3/`：问题三入口、附件、正式结果和图片。
- `problem4-3/`：问题四-3入口、附件、正式结果和图片。

## 运行

在本目录安装依赖后，可分别运行：

```bash
cd problem3
pip install -r requirements.txt
python problem3.py
python plot_problem3.py
```

```bash
cd problem4-3
pip install -r requirements.txt
python problem4.py
python plot_problem4.py
```

`problem3/` 中的 `result3.xlsx`、`dispatch_problem3.csv`、`scheme_summary.csv`
和 `figures/` 属于问题三；`problem4-3/` 中对应的 `result4-3.xlsx`、
`dispatch_problem4.csv`、`scheme_summary.csv` 和 `figures/` 属于问题四-3。
当前结果为完整评价期 2025-02-01 至 2025-12-31，共 334 天。
