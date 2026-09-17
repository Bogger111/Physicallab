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
    if method in ("curve", "higher_curve"):
        vals=_numbers(rows,"voltage","current"); x,y=map(list,zip(*vals))
        xlabel = "UKG1 / V" if method == "higher_curve" else "VG2K / V"
        title = "较高激发能级曲线" if method == "higher_curve" else "弗兰克-赫兹特性曲线"
        return {"data_points":len(vals),"current_max":max(y)},[],_plot(x,[(y,"实验曲线","#2563eb")],xlabel,"IP / nA",title,connect_points=True)
    if method == "parameter_curve":
        vals=_numbers(rows,"voltage","current_reference","current_variant")
        x,reference,variant=map(list,zip(*vals))
        differences=[abs(a-b) for a,b in zip(reference,variant)]
        return {"data_points":len(vals),"max_difference":max(differences)},[],_plot(
            x,[(reference,"基准参数","#2563eb"),(variant,"改变参数后","#f59e0b")],
            "VG2K / V","IP / nA","工作参数对曲线的影响",connect_points=True)
    peaks=[v[0] for v in _numbers(rows,"peak_voltage")]
    if len(peaks)<3: raise ValueError("至少需要 3 个连续峰值电压")
    diffs=[(peaks[i+3]-peaks[i])/3 for i in range(len(peaks)-3)] if len(peaks)>=6 else np.diff(peaks).tolist()
    v0=_mean(diffs)
    return {"v0":v0,"relative_error":abs(v0-4.90)/4.90*100,"spacing_std":_std(diffs)},[{"group":i+1,"delta_u":v} for i,v in enumerate(diffs)],_plot(list(range(1,len(peaks)+1)),[(peaks,"峰位","#dc2626")],"峰序","峰值电压 / V","峰值位置")


FORMULAS = {'curve': ['I_P=f(V_{G2K})'],
 'peaks': ['\\Delta U_i=\\frac{U_{p(i+3)}-U_{pi}}{3}',
           'V_0=\\overline{\\Delta U},\\quad E_r=\\frac{|V_0-4.90|}{4.90}\\times100\\%'],
 'parameter_curve': ['\\Delta I_i=I_{{\\rm variant},i}-I_{{\\rm reference},i}'],
 'higher_curve': ['I_P=f(U_{KG1})']}



EXPERIMENT = ConfiguredExperiment(
    experiment_id='franck-hertz',
    config=CONFIG,
    calculator=calculate,
    formulas=FORMULAS,
    public=False,
    legacy=True,
    catalogued=False,
)
