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
    if method == "waveform":
        vals=_numbers(rows,"sample_code","tail_count","t1","t2")
        return {"observed_rows":len(vals),
                "max_symmetry_error":max(abs(t1-t2) for _,_,t1,t2 in vals)},[],None
    vals=_numbers(rows,"frequency","field"); nu,b=map(list,zip(*vals)); f=_fit(b,nu); gamma=f["slope"]*1000; g=gamma/7.6225914; ref=5.5857 if method=="hydrogen" else 5.2567
    if method == "pure_water": ref=5.5857
    return {"gamma":gamma,"g_factor":g,"relative_error":abs(g-ref)/ref*100,"r_squared":f["r_squared"]},[],_plot(b,[(nu,r"$^1$H" if method=="hydrogen" else r"$^{19}$F","#2563eb")],"B0 / mT","ν / MHz","核磁共振线性拟合",True)


FORMULAS = {'waveform': ['\\Delta T=|T_1-T_2|'],
 'hydrogen': ['\\nu=kB_0+b,\\quad \\frac{\\gamma}{2\\pi}=10^3k', 'g=\\frac{\\gamma/(2\\pi)}{\\mu_N/h}'],
 'fluorine': ['\\nu=kB_0+b,\\quad \\frac{\\gamma}{2\\pi}=10^3k', 'g=\\frac{\\gamma/(2\\pi)}{\\mu_N/h}'],
 'pure_water': ['\\nu=kB_0+b,\\quad \\frac{\\gamma}{2\\pi}=10^3k', 'g=\\frac{\\gamma/(2\\pi)}{\\mu_N/h}']}



EXPERIMENT = ConfiguredExperiment(
    experiment_id='nmr',
    config=CONFIG,
    calculator=calculate,
    formulas=FORMULAS,
)
