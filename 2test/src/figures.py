"""从已保存的CSV结果生成三张单页矢量PDF，并执行结构验收。"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from pypdf import PdfReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas


PAGE = (720.0, 360.0)
MARGIN = (62.0, 42.0, 24.0, 38.0)  # 左、下、右、上


def _font() -> str:
    name = "Problem2Chinese"
    if name not in pdfmetrics.getRegisteredFontNames():
        candidates = [Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf")]
        path = next((p for p in candidates if p.exists()), None)
        if path is None:
            raise FileNotFoundError("找不到微软雅黑或黑体，无法生成中文PDF")
        pdfmetrics.registerFont(TTFont(name, str(path), subfontIndex=0))
    return name


def _read_daily(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _axes(canvas: Canvas, xlabel: str, ylabel: str, xlabels: list[str], ymax: float, font: str):
    left, bottom, right, top = MARGIN
    width, height = PAGE[0] - left - right, PAGE[1] - bottom - top
    canvas.setStrokeColorRGB(0.25, 0.25, 0.25)
    canvas.line(left, bottom, left, bottom + height)
    canvas.line(left, bottom, left + width, bottom)
    canvas.setFont(font, 9)
    for i in range(6):
        y = bottom + height * i / 5
        value = ymax * i / 5
        canvas.setStrokeColorRGB(0.88, 0.88, 0.88)
        canvas.line(left, y, left + width, y)
        canvas.setFillColorRGB(0.2, 0.2, 0.2)
        canvas.drawRightString(left - 6, y - 3, f"{value:,.0f}")
    step = width / max(1, len(xlabels))
    for i, label in enumerate(xlabels):
        canvas.drawCentredString(left + (i + 0.5) * step, bottom - 16, label)
    canvas.drawCentredString(left + width / 2, 10, xlabel)
    canvas.saveState()
    canvas.translate(13, bottom + height / 2)
    canvas.rotate(90)
    canvas.drawCentredString(0, 0, ylabel)
    canvas.restoreState()
    return left, bottom, width, height


def _monthly_bars(rows: list[dict[str, str]], target: Path, value_fields: list[str], labels: list[str], colors, ylabel: str):
    monthly = defaultdict(lambda: [0.0] * len(value_fields))
    for row in rows:
        if row["date"] < "2025-02-01":
            continue
        month = row["date"][5:7]
        for i, field in enumerate(value_fields):
            monthly[month][i] += float(row[field])
    months = sorted(monthly)
    ymax = max(sum(monthly[m]) for m in months) * 1.12 or 1.0
    font = _font(); canvas = Canvas(str(target), pagesize=PAGE, pageCompression=1)
    left, bottom, width, height = _axes(canvas, "月份", ylabel, [f"{int(m)}月" for m in months], ymax, font)
    group = width / len(months); barw = group * 0.58
    for j, month in enumerate(months):
        y0 = bottom
        for value, color in zip(monthly[month], colors):
            h = value / ymax * height
            canvas.setFillColorRGB(*color); canvas.rect(left + j * group + (group-barw)/2, y0, barw, h, fill=1, stroke=0)
            y0 += h
    canvas.setFont(font, 9)
    x = left
    for label, color in zip(labels, colors):
        canvas.setFillColorRGB(*color); canvas.rect(x, PAGE[1]-24, 10, 8, fill=1, stroke=0)
        canvas.setFillColorRGB(0.15,0.15,0.15); canvas.drawString(x+14, PAGE[1]-24, label); x += 110
    canvas.showPage(); canvas.save()


def _soc_line(rows: list[dict[str, str]], target: Path):
    points = [(row["date"], float(row["final_soc_kwh"])) for row in rows if row["date"] >= "2025-02-01"]
    font = _font(); canvas = Canvas(str(target), pagesize=PAGE, pageCompression=1)
    left, bottom, width, height = _axes(canvas, "日期（每月刻度）", "日末储电量 / kWh", [f"{m}月" for m in range(2,13)], 10800.0, font)
    canvas.setStrokeColorRGB(0.10,0.42,0.72); canvas.setLineWidth(1.2)
    path = canvas.beginPath()
    for i, (_, value) in enumerate(points):
        x=left+width*i/max(1,len(points)-1); y=bottom+height*value/10800.0
        (path.moveTo if i==0 else path.lineTo)(x,y)
    canvas.drawPath(path,stroke=1,fill=0)
    for bound,color,label in [(1200.0,(0.75,0.2,0.2),"下限 1200"),(10800.0,(0.2,0.55,0.25),"上限 10800")]:
        y=bottom+height*bound/10800.0; canvas.setStrokeColorRGB(*color); canvas.setDash(4,3); canvas.line(left,y,left+width,y)
        canvas.setFont(font,8); canvas.drawRightString(left+width,y+3,label)
    canvas.setDash(); canvas.showPage(); canvas.save()


def _validate(path: Path) -> None:
    reader = PdfReader(str(path))
    if len(reader.pages) != 1 or path.stat().st_size < 3000:
        raise AssertionError(f"PDF结构异常: {path}")
    resources = reader.pages[0].get("/Resources", {})
    if resources.get("/XObject"):
        raise AssertionError(f"图中含栅格XObject，未保持纯矢量: {path}")


def make_figures(base: Path) -> list[Path]:
    rows = _read_daily(base / "outputs" / "daily_summary.csv")
    target = base / "figures"; target.mkdir(parents=True, exist_ok=True)
    paths = [target/"problem2_monthly_cost.pdf", target/"problem2_monthly_emergency.pdf", target/"problem2_soc.pdf"]
    _monthly_bars(rows, paths[0], ["planned_cost_yuan","emergency_cost_yuan"], ["正常购电费","五倍紧急购电费"], [(0.22,0.48,0.72),(0.88,0.35,0.20)], "月费用 / 元")
    _monthly_bars(rows, paths[1], ["emergency_kwh"], ["紧急购电量"], [(0.88,0.35,0.20)], "紧急购电量 / kWh")
    _soc_line(rows, paths[2])
    for path in paths: _validate(path)
    return paths
