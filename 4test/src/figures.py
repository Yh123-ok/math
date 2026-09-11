"""从落盘CSV以ReportLab绘制中文纯矢量图。"""
import os
from pathlib import Path
import numpy as np
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from pypdf import PdfReader
from .reporting import read_csv

COLORS=((.2,.45,.7),(.85,.4,.2),(.15,.6,.4),(.6,.4,.7),(.6,.6,.2),(.8,.2,.4))


def axes(c,box,ymax,ylabel,xmax,xticks,xlabel):
    left,bottom,width,height=box;c.setFont('Chinese',9);c.setFillColorRGB(.15,.15,.15)
    for i in range(5):
        y=bottom+height*i/4;c.setStrokeColorRGB(.88,.88,.88);c.line(left,y,left+width,y)
        c.drawRightString(left-6,y-3,f'{ymax*i/4:.2f}' if ymax<10 else f'{ymax*i/4:,.0f}')
    c.setStrokeColorRGB(.3,.3,.3);c.setLineWidth(.6)
    c.line(left,bottom,left,bottom+height);c.line(left,bottom,left+width,bottom)
    for x,label in xticks:c.drawCentredString(left+width*x/xmax,bottom-15,label)
    c.drawCentredString(left+width/2,bottom-32,xlabel)
    c.saveState();c.translate(left-49,bottom+height/2);c.rotate(90)
    c.drawCentredString(0,0,ylabel);c.restoreState()


def line(c,box,x,y,xmax,ymax,color):
    left,bottom,width,height=box;c.setStrokeColorRGB(*color);c.setLineWidth(.85);path=c.beginPath()
    for i,(a,b) in enumerate(zip(x,y)):
        (path.moveTo if i==0 else path.lineTo)(left+width*a/xmax,bottom+height*b/ymax)
    c.drawPath(path,stroke=1,fill=0)


def legend(c,x,y,labels):
    c.setFont('Chinese',9)
    for j,label in enumerate(labels):
        c.setFillColorRGB(*COLORS[j]);c.rect(x+j*102,y,10,7,fill=1,stroke=0)
        c.setFillColorRGB(.15,.15,.15);c.drawString(x+j*102+14,y,label)


def create_figures(base):
    fonts=[Path(os.environ.get('PROBLEM4_FONT','C:/Windows/Fonts/msyh.ttc')),Path('C:/Windows/Fonts/simhei.ttf')]
    font=next((p for p in fonts if p.exists()),None)
    if font is None:raise FileNotFoundError('请设置PROBLEM4_FONT为中文TrueType字体路径')
    pdfmetrics.registerFont(TTFont('Chinese',str(font),subfontIndex=0))
    out=base/'figures';out.mkdir(exist_ok=True)
    daily=read_csv(base/'outputs/daily_summary.csv');rows=read_csv(base/'outputs/dispatch_all_year.csv')
    for metric,file,ylabel in [('total_cost_yuan','monthly_cost.pdf','总购电费用（万元）'),
        ('emergency_kwh','monthly_emergency.pdf','紧急购电量（万kWh）')]:
        values=np.array([[sum(float(r[metric]) for r in daily if r['strategy']==n and int(r['date'][5:7])==m)/10000
            for m in range(2,13)] for n in ('greedy','mpc','official')])
        c=Canvas(str(out/file),pagesize=(760,330));box=(65,48,665,238);ymax=values.max()*1.12
        axes(c,box,ymax,ylabel,11,[(i+.5,str(i+2)) for i in range(11)],'月份（2025年）')
        for j in range(3):
            c.setFillColorRGB(*COLORS[j])
            for i,v in enumerate(values[j]):c.rect(65+665*(i+.14+j*.24)/11,48,665*.22/11,238*v/ymax,fill=1,stroke=0)
        legend(c,65,307,['即时放电','价格感知MPC','正式历史选择']);c.showPage();c.save()
    day=[r for r in rows if r['date']=='2025-06-21'];x=np.arange(144)/6
    c=Canvas(str(out/'dispatch_june21.pdf'),pagesize=(760,690))
    specs=[((65,506,665,142),['price_yuan_per_kwh'],['电价'],'电价（元/kWh）'),
        ((65,275,665,165),['load_kwh','pv_kwh','plan_purchase_kwh','charge_kwh','discharge_kwh','emergency_kwh'],
         ['负载','光伏','计划购电','充电','放电','紧急购电'],'十分钟电量（kWh）'),
        ((65,52,665,158),['soc_start_kwh'],['储电量'],'储电量（kWh）')]
    for box,keys,labs,ylabel in specs:
        ymax=11400 if keys==['soc_start_kwh'] else max(float(r[k]) for r in day for k in keys)*1.12
        axes(c,box,ymax,ylabel,24,[(i,str(i)) for i in range(0,25,4)],'2025年6月21日时刻')
        for j,k in enumerate(keys):
            y=[float(r[k]) for r in day];xx=x
            if k=='soc_start_kwh':y.append(float(day[-1]['soc_end_kwh']));xx=np.arange(145)/6
            line(c,box,xx,y,24,ymax,COLORS[j])
        if keys==['soc_start_kwh']:
            c.setDash(4,3)
            for bound in (1200,10800):line(c,box,[0,24],[bound,bound],24,ymax,(.5,.5,.5))
            c.setDash()
        legend(c,65,box[1]+box[3]+10,labs)
    c.showPage();c.save()
    grid=np.array([float(r['soc_end_kwh']) for r in rows]).reshape(365,144)[31:]
    c=Canvas(str(out/'soc.pdf'),pagesize=(760,350));box=(65,48,665,250)
    import datetime
    start=datetime.date(2025,2,1)
    ticks=[((datetime.date(2025,m,1)-start).days,f'{m}月') for m in range(2,13)]
    axes(c,box,11400,'储电量（kWh）',333,ticks,'日期（2025年）')
    for j,y in enumerate((grid.min(axis=1),grid.max(axis=1),grid[:,-1])):line(c,box,np.arange(334),y,333,11400,COLORS[j])
    c.setDash(4,3)
    for bound in (1200,10800):
        line(c,box,[0,333],[bound,bound],333,11400,(.5,.5,.5))
        c.setFont('Chinese',8);c.drawRightString(730,48+250*bound/11400+4,str(bound))
    c.setDash();legend(c,65,325,['日内最低','日内最高','每日24:00']);c.showPage();c.save()
    for path in out.glob('*.pdf'):
        pdf=PdfReader(path);assert len(pdf.pages)==1 and path.stat().st_size>3000
        assert not pdf.pages[0].get('/Resources',{}).get('/XObject'), '应为纯矢量PDF'
