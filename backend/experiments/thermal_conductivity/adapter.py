from __future__ import annotations

import base64
import io
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from experiments.core.configured import ConfiguredExperiment
from experiments.core.numerics import (calibration as _calibration, fit as _fit,
                                       mean as _mean, numbers as _numbers,
                                       plot as _plot, std as _std)
from experiments.schema import enrich_config


CONFIG = enrich_config(json.loads(Path(__file__).with_name("config.json").read_text(encoding="utf-8")))


def calculate(method, rows, p):
    if method == "geometry":
        vals=_numbers(rows,"dc","hc","db","hb"); cols=list(zip(*vals)); keys=("dc_mean","hc_mean","db_mean","hb_mean")
        return {k:_mean(v) for k,v in zip(keys,cols)},[],None
    if method == "heating":
        vals=_numbers(rows,"time","ta","tc"); t,ta,tc=map(list,zip(*vals)); last=min(5,len(vals)); t1=_mean(ta[-last:]); t2=_mean(tc[-last:]); drift=max(max(ta[-last:])-min(ta[-last:]),max(tc[-last:])-min(tc[-last:]))
        return {"t1":t1,"t2":t2,"steady_drift":drift},[],_plot(t,[(ta,"上盘 TA","#dc2626"),(tc,"下盘 TC","#2563eb")],"t / min","T / °C","升温与稳态过程",connect_points=True)
    vals=_numbers(rows,"time","temperature"); t,temp=map(np.asarray,zip(*vals)); target=p.get("t2",35); order=np.argsort(np.abs(temp-target))[:min(10,len(temp))]; f=_fit(t[order],temp[order]); rate=abs(f["slope"]); m=p.get("mass",500)/1000; c=p.get("specific_heat",394); rc=p.get("dc",100)/2000; hc=p.get("hc",10)/1000; rb=p.get("db",100)/2000; hb=p.get("hb",8)/1000; dt=p.get("t1",50)-p.get("t2",35); xi=(2*rc+hc)/(2*rc+2*hc); lam=m*c*rate*hb/(math.pi*rb*rb*dt)*xi
    return {"cooling_rate":rate,"lambda":lam,"geometry_factor":xi,"r_squared":f["r_squared"]},[],_plot(t.tolist(),[(temp.tolist(),"冷却曲线","#2563eb")],"t / s","TC / °C","自然冷却曲线",connect_points=True,fit_indices=order.tolist())


FORMULAS = {'geometry': ['\\overline{x}=\\frac{1}{n}\\sum_i x_i'],
 'heating': ['T_1=\\overline{T_A},\\quad T_2=\\overline{T_C}'],
 'cooling': ['\\xi=\\frac{2R_C+h_C}{2R_C+2h_C}', '\\lambda=\\frac{mc|dT/dt|_{T_2}h_B}{\\pi R_B^2(T_1-T_2)}\\xi']}



EXPERIMENT = ConfiguredExperiment(
    experiment_id='thermal-conductivity',
    config=CONFIG,
    calculator=calculate,
    formulas=FORMULAS,
)
