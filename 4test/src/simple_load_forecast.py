"""Causal load forecast: daily level times recent same-type intraday shape.

The two low-load weekdays are identified exactly once on January 15 from
January 1-14. No future day is used to label or forecast an earlier day.
"""
import numpy as np


def forecast_load(dates,load):
    n=len(dates)
    result=np.zeros_like(load,dtype=float)
    totals=load.sum(axis=1)
    low_days=None
    for d in range(1,n):
        if d==14:
            weekday_means=[np.mean([totals[i] for i in range(14)
                if dates[i].weekday()==j]) for j in range(7)]
            low_days=set(int(x) for x in np.argsort(weekday_means)[:2])
        allowed=low_days if low_days is not None else {5,6}
        def kind(i):return int(dates[i].weekday() not in allowed)
        category=kind(d)
        same=[i for i in range(d-1,-1,-1) if kind(i)==category][:3]
        if not same:same=[d-1]
        shape=load[same].sum(axis=0)/max(float(totals[same].sum()),1e-12)
        switch=[i for i in range(max(1,d-35),d) if kind(i)!=kind(i-1)]
        transitions=[np.log(totals[i]/totals[i-1])/(kind(i)-kind(i-1)) for i in switch]
        beta=float(np.median(transitions)) if transitions else 0.
        predicted_total=totals[d-1]*np.exp(beta*(category-kind(d-1)))
        result[d]=predicted_total*shape
    return result
