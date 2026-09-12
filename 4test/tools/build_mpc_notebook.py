"""Embed the complete plotting source into an executable competition notebook."""
from pathlib import Path
import nbformat
BASE=Path(__file__).resolve().parents[1]


def build():
    source=(BASE/'src'/'plot_mpc.py').read_text(encoding='utf-8')
    source=source.split("if __name__=='__main__':create_figures()")[0]
    note=nbformat.v4.new_notebook()
    note.cells=[
        nbformat.v4.new_markdown_cell('# 第四问重解第二问：正式结果绘图\n\n全部绘图代码在下方单元格；仅读取保存的CSV。'),
        nbformat.v4.new_code_cell(source),
        nbformat.v4.new_code_cell("create_figures()\nfrom IPython.display import display, Image\nfor name in ('cost_comparison','monthly_cost_emergency','forecast_accuracy','dispatch_june21'):\n    display(Image(filename=str(Path(os.environ.get('PROBLEM4_FIGURE_DIR',str(locate()/'figures')))/(name+'.png'))))")]
    note.metadata['kernelspec']={'display_name':'Python 3','language':'python','name':'python3'}
    dest=BASE/'notebooks'/'mpc_analysis.ipynb';dest.parent.mkdir(exist_ok=True)
    nbformat.write(note,dest);return dest


if __name__=='__main__':print(build())
