"""将绘图源码按章节写入Notebook，保证Notebook含完整可读绘图代码。"""
from pathlib import Path
import nbformat

BASE=Path(__file__).resolve().parents[1]


def build():
    source=(BASE/'src/plot_analysis.py').read_text(encoding='utf-8')
    cells=[nbformat.v4.new_markdown_cell('# 第四问：联合选择结果与图表复现\n\n'
        '按顺序运行全部单元格。只读取保存的CSV，不重新预测或调参。下方包含完整Matplotlib源码，'
        '与src/plot_analysis.py保持一致。输出中文矢量PDF和PNG。\n\n'
        '**信息边界：**评分热图来自每次决策前已结束的历史窗口；全年费用散点和压力日仅用于事后诊断。'
        '同起点联合策略预先确定为正式规则，不能按全年图表倒选历史策略。\n\n'
        '|风险编号|alpha|kappa|\n|---|---:|---:|\n|0|0.80|1.00|\n|1|0.85|0.80|\n'
        '|2|0.90|0.70|\n|3|0.90|0.80|\n|4|0.95|0.60|\n|5|0.95|0.70|\n\n'
        '图中“4·M”表示风险4配MPC；G表示即时放电，M表示MPC。组合编号从0起：2×风险编号+控制器编号，G为0、M为1。')]
    for chunk in source.split('# %%'):
        if not chunk.strip():continue
        if chunk.startswith('"""'):
            continue
        title,code=chunk.split('\n',1)
        cells.append(nbformat.v4.new_markdown_cell('## '+title.strip()))
        cells.append(nbformat.v4.new_code_cell(code.strip()))
    cells.extend([nbformat.v4.new_markdown_cell('## 定位数据与输出目录\n\n'
        '通常从4test或notebooks目录运行。环境变量仅供验收时将复现图写入独立目录，正常使用无需设置。'),
        nbformat.v4.new_code_cell("start=Path.cwd().resolve()\n"
            "candidates=[p for parent in (start,*start.parents) for p in (parent,parent/'4test')]\n"
            "BASE=next(p for p in candidates if (p/'outputs/selection_scores.csv').exists())\n"
            "FIGURES=Path(os.environ.get('PROBLEM4_FIGURE_DIR',str(BASE/'figures')))\n"
            "style()\ndata=read_data(BASE)\n"
            "display(data['summary'][['label','total_cost_yuan','savings_vs_layered_yuan','emergency_kwh']])")])
    plots=[('费用构成与相对节省','plot_cost_comparison(data,FIGURES)','cost_comparison'),
        ('月度和累计节省','plot_monthly_cost(data,FIGURES)','monthly_cost'),
        ('紧急电量和支付单价','plot_emergency(data,FIGURES)','monthly_emergency'),
        ('组合选择轨迹','plot_selection(data,FIGURES)','selection_timeline'),
        ('历史评分全貌','plot_historical_scores(data,FIGURES)','historical_scores'),
        ('参数与控制器交互','plot_interaction(data,FIGURES)','parameter_controller_interaction'),
        ('事后费用与电量权衡','plot_tradeoff(data,FIGURES)','candidate_tradeoff'),
        ('6月21日调度',"plot_dispatch(data,FIGURES,'2025-06-21','dispatch_june21')",'dispatch_june21'),
        ('紧急电量最高日：仅作事后诊断',"stress=data['dispatch'].groupby('date').emergency_kwh.sum().idxmax()\nprint('压力日：',stress)\nplot_dispatch(data,FIGURES,stress,'dispatch_stress_day')",'dispatch_stress_day'),
        ('库存范围及边界','plot_soc(data,FIGURES)','soc')]
    for title,call,name in plots:
        cells.append(nbformat.v4.new_markdown_cell('## '+title))
        cells.append(nbformat.v4.new_code_cell(call+f"\nfrom IPython.display import Image,display\ndisplay(Image(filename=str(FIGURES/'{name}.png')))") )
    book=nbformat.v4.new_notebook(cells=cells,metadata={'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'},
        'language_info':{'name':'python','version':'3.12'}})
    folder=BASE/'notebooks';folder.mkdir(exist_ok=True)
    path=folder/'analysis_plots.ipynb';nbformat.write(book,path)
    return path


if __name__=='__main__':print(build())
