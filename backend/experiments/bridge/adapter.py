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
    if method == "balanced":
        vals = [v[0] for v in _numbers(rows, "rn")]
        rx = [p.get("ra", 1000) / p.get("rb", 5000) * v for v in vals]
        mean = _mean(rx)
        return {"rx_mean": mean, "relative_error": abs(mean - 50) / 50 * 100}, \
            [{"rn": a, "rx": b} for a, b in zip(vals, rx)], None
    if method == "cu50":
        vals = _numbers(rows, "temperature", "u0")
        t, u_mv = map(list, zip(*vals)); us = p.get("us", 3); r = p.get("r", 1000); rn = p.get("rn", 50)
        u = np.asarray(u_mv) / 1000
        if np.any(us - 2 * u <= 0): raise ValueError("U0 必须满足 Us-2U0>0")
        rx = rn + 4 * r * u / (us - 2 * u)
        f = _fit(t, rx)
        alpha = f["slope"] / f["intercept"]
        result = {"r0": f["intercept"], "alpha": alpha, "r_squared": f["r_squared"],
                  "alpha_error": abs(alpha - .004280) / .004280 * 100}
        derived = [{"temperature": a, "u0": b, "rx": float(c)} for a, b, c in zip(t, u_mv, rx)]
        return result, derived, _plot(t, [(rx.tolist(), "Cu50", "#dc2626")], "t / °C", "Rx / Ω", "Cu50 阻温特性", True)
    if method == "capacitor":
        vals = _numbers(rows, "cn", "rn"); ra=p.get("ra",100); rb=p.get("rb",120); f=p.get("f",1000)
        derived=[{"cn":cn,"rn":rn,"cx":rb/ra*cn,"rc":ra/rb*rn,"tan_delta":2*math.pi*f*cn*1e-6*rn} for cn,rn in vals]
        return {k:_mean([d[k] for d in derived]) for k in ("cx","rc","tan_delta")}, derived, None
    if method == "inductor":
        vals = _numbers(rows, "cn", "rn"); ra=p.get("ra",100); rb=p.get("rb",100); f=p.get("f",1000)
        derived=[{"cn":cn,"rn":rn,"lx":ra*rb*cn*1e-3,"rl":ra/rb*rn,"q":2*math.pi*f*rb*rb*cn*1e-6/rn} for cn,rn in vals if rn]
        return {k:_mean([d[k] for d in derived]) for k in ("lx","rl","q")}, derived, None
    vals=_numbers(rows,"temperature","resistance"); t,r=map(np.asarray,zip(*vals)); x=1/(t+273.15); y=np.log(r); f=_fit(x,y)
    return {"b_constant":f["slope"],"r_squared":f["r_squared"]}, [], _plot(x.tolist(),[(y.tolist(),"热敏电阻","#f59e0b")],r"1/T / K$^{-1}$","ln R","热敏电阻线性化",True)


FORMULAS = {'balanced': ['R_x=\\frac{R_a}{R_b}R_n'],
 'cu50': ['\\Delta R_x=\\frac{4RU_0}{U_s-2U_0},\\quad R_x=R_n+\\Delta R_x',
          'R_x=R_0(1+\\alpha t),\\quad \\alpha=\\frac{k}{R_0}'],
 'capacitor': ['C_x=\\frac{R_b}{R_a}C_n,\\quad r_C=\\frac{R_a}{R_b}R_n', '\\tan\\delta=2\\pi fC_nR_n'],
 'inductor': ['L_x=R_aR_bC_n,\\quad r_L=\\frac{R_a}{R_b}R_n', 'Q=\\frac{2\\pi fR_b^2C_n}{R_n}'],
 'thermistor': ['\\ln R=\\ln R_0+B\\left(\\frac{1}{T}-\\frac{1}{T_0}\\right)']}



EXPERIMENT = ConfiguredExperiment(
    experiment_id='bridge',
    config=CONFIG,
    calculator=calculate,
    formulas=FORMULAS,
)
