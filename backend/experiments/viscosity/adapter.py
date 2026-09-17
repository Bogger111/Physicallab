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
    if method == "diameter":
        vals=_numbers(rows,"x1","x2"); ds=[abs(a-b) for a,b in vals]
        return {"diameter":_mean(ds),"diameter_std":_std(ds)},[{"x1":a,"x2":b,"diameter":abs(a-b)} for a,b in vals],_plot(list(range(1,len(ds)+1)),[(ds,"直径","#2563eb")],"测量序号","d / mm","钢球直径重复测量")
    if method == "diameter_effect":
        vals=[]
        for row in rows:
            try:
                diameter=float(row["diameter"])
                times=[float(row[k]) for k in ("t1","t2","t3","t4") if row.get(k) not in (None,"")]
            except (ValueError,TypeError,KeyError):
                continue
            if times: vals.append((diameter,_mean(times)))
        L=p.get("distance",20)/100; rho=p.get("rho_ball",7800); rho0=p.get("rho_oil",950)
        D=p.get("tube_diameter",2)/100; g=p.get("g",9.794); derived=[]
        for diameter,t_mean in vals:
            d=diameter/1000; velocity=L/t_mean
            eta=g*d*d*(rho-rho0)/(18*velocity*(1+2.4*d/D))
            re=rho0*velocity*d/eta
            corrected=eta if re<.1 else eta*(1-3*re/16) if re<1 else eta
            derived.append({"diameter":diameter,"t_mean":t_mean,"velocity":velocity,
                            "eta":eta,"re":re,"eta_corrected":corrected})
        return {"sample_count":len(derived),
                "eta_mean":_mean([item["eta_corrected"] for item in derived]),
                "re_max":max(item["re"] for item in derived)},derived,_plot(
                    [item["diameter"] for item in derived],
                    [([item["re"] for item in derived],"Re","#7c3aed")],
                    "d / mm","Re","球径与雷诺数",connect_points=True)
    vals=[]
    for row in rows:
        try: temp=float(row["temperature"]); ts=[float(row[k]) for k in ("t1","t2","t3","t4") if row.get(k) not in (None,"")]
        except (ValueError,TypeError,KeyError): continue
        if ts: vals.append((temp,_mean(ts)))
    L=p.get("distance",20)/100; d=p.get("diameter",1.5)/1000; rho=p.get("rho_ball",7800); rho0=p.get("rho_oil",950); D=p.get("tube_diameter",2)/100; g=p.get("g",9.794); derived=[]
    for temp,t in vals:
        v=L/t; eta=g*d*d*(rho-rho0)/(18*v*(1+2.4*d/D)); re=rho0*v*d/eta; corrected=eta if re<.1 else eta*(1-3*re/16) if re<1 else eta
        derived.append({"temperature":temp,"t_mean":t,"velocity":v,"eta":eta,"re":re,"eta_corrected":corrected})
    return {"eta_20":derived[0]["eta_corrected"],"re_min":min(d["re"] for d in derived),"re_max":max(d["re"] for d in derived)},derived,_plot([d["temperature"] for d in derived],[([d["eta_corrected"] for d in derived],"η′","#dc2626")],"T / °C","η′ / Pa·s","粘滞系数与温度",connect_points=True)


FORMULAS = {'diameter': ['d_i=|x_{2,i}-x_{1,i}|,\\quad \\overline{d}=\\frac{1}{n}\\sum_i d_i'],
 'viscosity': ['v_0=\\frac{L}{\\overline{t}}',
               '\\eta_0=\\frac{gd^2(\\rho-\\rho_0)}{18v_0(1+2.4d/D)}',
               "Re=\\frac{\\rho_0v_0d}{\\eta_0},\\quad \\eta'=\\eta_0\\left(1-\\frac{3}{16}Re\\right)"],
 'diameter_effect': ['v_0=\\frac{L}{\\overline{t}}', 'Re=\\frac{\\rho_0v_0d}{\\eta_0}']}



EXPERIMENT = ConfiguredExperiment(
    experiment_id='viscosity',
    config=CONFIG,
    calculator=calculate,
    formulas=FORMULAS,
)
