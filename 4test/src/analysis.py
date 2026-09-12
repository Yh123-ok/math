"""从已保存CSV生成比较表和说明；不影响任何历史决策。"""
import json
import numpy as np
import pandas as pd
from .reporting import write_csv

LABELS={'greedy':'原G对照','mpc':'原MPC对照','layered':'原分层选择',
    'joint':'连续联合选择','official':'同起点联合选择（正式）'}


def analyze_results(base):
    out=base/'outputs'
    daily=pd.read_csv(out/'daily_summary.csv');daily=daily[daily.date>='2025-02-01'].copy()
    summary=pd.read_csv(out/'summary.csv').set_index('strategy')
    baseline=summary.loc['layered'];comparisons=[]
    for name,r in summary.iterrows():
        comparisons.append({'strategy':name,'label':LABELS[name],**r.to_dict(),
            'savings_vs_layered_yuan':baseline.total_cost_yuan-r.total_cost_yuan,
            'savings_vs_layered_pct':100*(baseline.total_cost_yuan-r.total_cost_yuan)/baseline.total_cost_yuan,
            'emergency_change_vs_layered_kwh':r.emergency_kwh-baseline.emergency_kwh,
            'average_emergency_price_yuan_per_kwh':r.emergency_cost_yuan/r.emergency_kwh if r.emergency_kwh else 0})
    write_csv(out/'strategy_comparison.csv',comparisons)
    daily['month']=daily.date.str[:7]
    fields=['planned_cost_yuan','emergency_cost_yuan','total_cost_yuan','emergency_kwh','plan_purchase_kwh']
    monthly=daily.groupby(['strategy','month'],sort=False)[fields].sum().reset_index()
    reference=monthly[monthly.strategy=='layered'].set_index('month').total_cost_yuan
    monthly['savings_vs_layered_yuan']=monthly.month.map(reference)-monthly.total_cost_yuan
    monthly['average_emergency_price']=monthly.emergency_cost_yuan/monthly.emergency_kwh.replace(0,np.nan)
    monthly.to_csv(out/'monthly_comparison.csv',index=False,encoding='utf-8-sig')
    shadow=pd.read_csv(out/'risk_shadow_daily.csv');shadow=shadow[shadow.date>='2025-02-01']
    candidates=shadow.groupby(['combo','risk_index','controller'],sort=True)[fields].sum().reset_index()
    candidates['cost_minus_layered_yuan']=candidates.total_cost_yuan-baseline.total_cost_yuan
    candidates.to_csv(out/'candidate_comparison.csv',index=False,encoding='utf-8-sig')
    scores=pd.read_csv(out/'selection_scores.csv')
    rows=[]
    for selector,group in scores.groupby('selector'):
        for combo,g in group.groupby('combo'):
            rows.append({'selector':selector,'combo':int(combo),'selected_updates':int(g.selected.sum()),
                'mean_score_gap_yuan':float((g.score-group.groupby('date').score.transform('min').loc[g.index]).mean())})
    write_csv(out/'selection_frequency.csv',rows)
    formal=next(r for r in comparisons if r['strategy']=='official')
    joint=next(r for r in comparisons if r['strategy']=='joint')
    selected=scores[scores.selected==1].pivot(index='date',columns='selector',values='combo')
    disagree=int((selected.same_start!=selected.continuous).sum())
    official_months=monthly[monthly.strategy=='official']
    improved=int((official_months.savings_vs_layered_yuan>0).sum())
    report=['# 联合选择改进与图表解读','',
        '所有方案使用相同输入、预测器、6组参数、每7日更新与28日评分窗口。正式策略在本轮求解前指定为同起点12组合联合选择，没有按全年结果倒选方案。','',
        '## 1. 结果对比','',
        '|策略|总费/元|比原分层节省/元|紧急量/kWh|紧急量变化/kWh|紧急平均单价/元每kWh|',
        '|---|---:|---:|---:|---:|---:|']
    for r in comparisons:
        report.append('|'+r['label']+'|'+'|'.join(f'{r[k]:.2f}' for k in ('total_cost_yuan','savings_vs_layered_yuan','emergency_kwh','emergency_change_vs_layered_kwh','average_emergency_price_yuan_per_kwh'))+'|')
    report.extend(['',f"同起点正式方案相对原分层节省 {formal['savings_vs_layered_yuan']:.2f} 元（{formal['savings_vs_layered_pct']:.4f}%）；紧急电量变化 {formal['emergency_change_vs_layered_kwh']:+.2f} kWh。负节省表示费用上升，不改名为优化收益。",
        f"连续联合方案相对原分层节省 {joint['savings_vs_layered_yuan']:.2f} 元。同起点和连续联合在 {len(selected)} 次更新中有 {disagree} 次选择不同。正式方案在11个月中有 {improved} 个月费用低于原分层。",'',
        ('本次两种联合规则的选择完全一致，最终调度及费用相同；共同起点重放没有带来额外收益。这说明此数据上库存起点差异未改变赢家，不能据此断言其他年份也相同。' if disagree==0 else
         '两种联合规则存在不同选择；库存与后续计划也会因此变化，不能将费用差全部归因于单个参数。')+
        '固定候选全年散点只是事后描述，不作为任何历史选项的评分输入。','',
        '## 2. 图表阅读顺序','',
        '|图|说明|','|---|---|',
        '|cost_comparison.pdf|正常与紧急费用分解；单独显示相对原分层节省额，避免总费用量级掩盖差异|',
        '|monthly_cost.pdf|月度节省与累计节省，显示改善是否持续|',
        '|monthly_emergency.pdf|月紧急量、平均紧急单价，分清少买与买便宜|',
        '|selection_timeline.pdf|风险/控制器组合选择轨迹及排名前两名分差|',
        '|historical_scores.pdf|每次更新的12候选历史分差；只展示已结束窗口|',
        '|parameter_controller_interaction.pdf|同参数下G与MPC历史评分差，检查分层近似；选择次数|',
        '|candidate_tradeoff.pdf|12固定组合及动态策略的费用—紧急量权衡（事后描述）|',
        '|dispatch_june21.pdf|题面6月21日价格、供需、电池充放电与库存|',
        '|dispatch_stress_day.pdf|正式策略紧急电量最多一天的诊断，仅事后选图，不参与调参|',
        '|soc.pdf|日内库存范围、日末库存与1200/10800边界|','',
        '## 3. 复现与边界','',
        '图来自outputs中已保存CSV，Notebook包含完整绘图代码，不重新求解模型。PDF与PNG固定样式并移除时间戳元数据，同环境可逐字节复现；验证记录见notebook_reproduction.json。',
        '历史同起点重放只接收更新日前的数组切片，所有历史日期使用当时的预测与价格代理。正式策略切换后仍沿用自己的当前库存，不复制重放末库存。',
        '这仍是已有数据上的历史因果回测，不能称独立盲测。12点是固定有限候选，不是连续参数空间的全局最优。'])
    (base/'reports/OPTIMIZATION_ANALYSIS.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    return comparisons
