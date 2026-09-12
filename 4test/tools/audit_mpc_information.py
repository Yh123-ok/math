"""Perturb actual future inputs and verify the official simple MPC information boundary."""
from pathlib import Path
import json
import sys
import numpy as np
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from src.data_io import read_inputs
from src.forecasting import generate_causal_forecasts,weighted_safety_margin
from src.simple_load_forecast import forecast_load
from src.day_ahead import historical_price_value,solve_plan
from src.realtime import execute_day


def main():
    data=read_inputs(BASE.parent)
    old=generate_causal_forecasts(data.dates,data.load,data.pv)
    candidate=forecast_load(data.dates,data.load)
    cutoff=31
    old_mae=float(np.mean(abs(old['load_final'][14:cutoff]-data.load[14:cutoff])))
    new_mae=float(np.mean(abs(candidate[14:cutoff]-data.load[14:cutoff])))
    assert new_mae<old_mae
    load=old['load_final'].copy();load[cutoff:]=candidate[cutoff:]
    point=load-old['pv_final'];error=(data.load-data.pv)-point
    maximum={'current_day_actual_to_forecast_kwh':0.,'current_day_actual_to_plan_kwh':0.,
        'future_price_to_plan_kwh':0.,'future_intraday_actual_to_past_action_kwh':0.}
    for d in (40,171,354):
        changed_load=data.load[:d+2].copy();changed_pv=data.pv[:d+2].copy()
        changed_load[d:]=changed_load[d:]*3+1000
        changed_pv[d:]=changed_pv[d:]*.1
        changed=generate_causal_forecasts(data.dates[:d+2],changed_load,changed_pv)
        load2=forecast_load(data.dates[:d+2],changed_load)
        assert abs(np.mean(abs(changed['load_final'][14:cutoff]-changed_load[14:cutoff]))-old_mae)<1e-12
        assert abs(np.mean(abs(load2[14:cutoff]-changed_load[14:cutoff]))-new_mae)<1e-12
        load2[:cutoff]=changed['load_final'][:cutoff]
        point2=load2-changed['pv_final']
        maximum['current_day_actual_to_forecast_kwh']=max(maximum['current_day_actual_to_forecast_kwh'],
            float(np.max(abs(point[d]-point2[d]))))
        error2=(changed_load-changed_pv)-point2
        q1=point[d]+weighted_safety_margin(d,error,.8)
        q2=point2[d]+weighted_safety_margin(d,error2,.8)
        value=historical_price_value(data.prices[:d],data.prices[d])
        # The reference initial inventory is already known at 0:00; choosing
        # one valid common value is sufficient for this input-dependency test.
        a=solve_plan(q1,data.prices[d],6000.,value)
        b=solve_plan(q2,data.prices[d],6000.,value)
        maximum['current_day_actual_to_plan_kwh']=max(maximum['current_day_actual_to_plan_kwh'],
            float(np.max(abs(a['q']-b['q']))))
        p2=data.prices.copy();p2[d+1:]*=9
        c=solve_plan(q1,p2[d],6000.,historical_price_value(p2[:d],p2[d]))
        maximum['future_price_to_plan_kwh']=max(maximum['future_price_to_plan_kwh'],
            float(np.max(abs(a['q']-c['q']))))
        net=data.load[d]-data.pv[d]
        changed_net=net.copy();changed_net[73:]+=9000
        x=execute_day(net,a,point[d],data.prices[d],6000.,'mpc')
        y=execute_day(changed_net,a,point[d],data.prices[d],6000.,'mpc')
        maximum['future_intraday_actual_to_past_action_kwh']=max(
            maximum['future_intraday_actual_to_past_action_kwh'],
            max(float(np.max(abs(x[k][:73]-y[k][:73]))) for k in ('charge','discharge','emergency','waste')))
    assert max(maximum.values())<=1e-6,maximum
    result={'dates_tested':['2025-02-10','2025-06-21','2025-12-21'],
            'max_effects':maximum,'passed':True,'scope':'tested input perturbations, not an independent blind dataset'}
    result['january_only_model_selection']={'old_mae_kwh':old_mae,'daily_shape_mae_kwh':new_mae,
        'selected':'daily_shape','selected_at':'2025-02-01 00:00'}
    (BASE/'outputs'/'official_causality.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
