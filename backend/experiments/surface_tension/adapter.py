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
    if method == "calibration":
        vals=_numbers(rows,"mass","u_up","u_down"); m,up,down=map(list,zip(*vals)); force=[v/1000*p.get("g",9.79338) for v in m]; mean_u=[(a+b)/2 for a,b in zip(up,down)]; f=_fit(force,mean_u)
        return {"sensitivity":abs(f["slope"]),"r_squared":f["r_squared"],"hysteresis":max(abs(a-b) for a,b in zip(up,down))},[],_plot(force,[(mean_u,"平均电压","#2563eb")],"F / N","U / mV","力敏传感器定标",True)
    if method in ("pull_off", "salt_pull_off"):
        vals=_numbers(rows,"u1","u2"); k=abs(float(p.get("sensitivity",1000))); circumference=math.pi*(p.get("d1",3.31)+p.get("d2",3.496))/100
        if k == 0: raise ValueError("力敏传感器灵敏度 K 不能为 0")
        sigmas=[abs(a-b)/k/circumference for a,b in vals]; sigma=_mean(sigmas)
        result={"sigma":sigma,"sigma_std":_std(sigmas),"sensitivity_used":k}
        if method == "pull_off" or "sigma_reference" in p:
            reference=abs(float(p.get("sigma_reference",.07275)))
            if reference == 0: raise ValueError("纯水标准值 σ0 不能为 0")
            result.update({"sigma_reference":reference,"absolute_error":abs(sigma-reference),
                           "relative_error":abs(sigma-reference)/reference*100})
        return result,[{"delta_u":abs(a-b),"sigma":s} for (a,b),s in zip(vals,sigmas)],_plot(list(range(1,len(sigmas)+1)),[(sigmas,"拉脱法","#7c3aed")],"测量序号",r"σ / N·m$^{-1}$","拉脱法重复测量")
    vals=_numbers(rows,"y1","y2","x1","x2"); hs=[abs(a-b) for a,b,_,_ in vals]; ds=[abs(c-d) for _,_,c,d in vals]; h=_mean(hs); d=_mean(ds); sigma=.25*p.get("density",998)*p.get("g",9.79338)*(d/1000)*(h/1000+d/6000)
    result={"sigma":sigma,"height":h,"diameter":d}
    if method == "capillary" or "sigma_reference" in p:
        reference=abs(float(p.get("sigma_reference",.07275)))
        if reference == 0: raise ValueError("纯水标准值 σ0 不能为 0")
        result.update({"sigma_reference":reference,"absolute_error":abs(sigma-reference),
                       "relative_error":abs(sigma-reference)/reference*100})
    return result,[{"height":hh,"diameter":dd} for hh,dd in zip(hs,ds)],_plot(list(range(1,len(hs)+1)),[(hs,"液柱高","#2563eb"),(ds,"内径","#f59e0b")],"测量序号","mm","毛细管读数")

def _prepare_params(method_id, params, results):
    if method_id in ("pull_off", "salt_pull_off"):
        calibrated = results.get("calibration", {}).get("sensitivity")
        if calibrated is not None:
            params["sensitivity"] = calibrated
    return params


def _extra_analysis(method_id, result):
    if method_id not in ("pull_off", "capillary"):
        return []
    from experiments.core.documents import fmt, safe_text
    return [{"kind": "para", "text": safe_text(
        f"最终结果：σ = ({fmt(result.get('sigma'))} ± {fmt(result.get('absolute_error'))}) N/m；"
        f"相对误差 Er = {fmt(result.get('relative_error'))}%。"
    )}]



FORMULAS = {'calibration': ['F=mg,\\quad U=KF+b'],
 'pull_off': ['\\sigma=\\frac{|U_1-U_2|}{\\pi(D_1+D_2)K}',
              '\\Delta\\sigma=|\\sigma-\\sigma_0|,\\quad E_r=\\frac{|\\sigma-\\sigma_0|}{\\sigma_0}\\times100\\%'],
 'capillary': ['h=|y_1-y_2|,\\quad d=|x_1-x_2|',
               '\\sigma=\\frac{1}{4}\\rho gd\\left(h+\\frac{d}{6}\\right)',
               '\\Delta\\sigma=|\\sigma-\\sigma_0|,\\quad E_r=\\frac{|\\sigma-\\sigma_0|}{\\sigma_0}\\times100\\%'],
 'salt_pull_off': ['\\sigma=\\frac{|U_1-U_2|}{\\pi(D_1+D_2)K}'],
 'salt_capillary': ['\\sigma=\\frac{1}{4}\\rho gd\\left(h+\\frac{d}{6}\\right)']}



EXPERIMENT = ConfiguredExperiment(
    experiment_id='surface-tension',
    config=CONFIG,
    calculator=calculate,
    formulas=FORMULAS,
    prepare_params=_prepare_params,
    extra_analysis=_extra_analysis,
)
