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
    if method == "transfer":
        vals=_numbers(rows,"excitation","output"); current,out=map(list,zip(*vals)); b=[.31416*v for v in current]; f=_fit(b,out)
        return {"sensitivity":f["slope"],"r_squared":f["r_squared"],"b_max":max(map(abs,b))},[{"field":x,"output":y} for x,y in zip(b,out)],_plot(b,[(out,"磁电转换","#2563eb")],"B / Gs","Vout / mV","GMR 磁电转换",fit_lines=True,connect_points=True)
    if method == "resistance":
        vals=_numbers(rows,"excitation","ir_a","ir_b"); supply=p.get("supply",2); b=[.31416*v[0] for v in vals]; ra=[2*supply/(v[1]/1000) for v in vals]; rb=[2*supply/(v[2]/1000) for v in vals]
        g=lambda r:(max(r)-min(r))/min(r)*100
        ga,gb=g(ra),g(rb)
        return {"gmr_a":ga,"gmr_b":gb,"sensitive_state":1 if ga>=gb else 2},[{"field":x,"ra":a,"rb":bb} for x,a,bb in zip(b,ra,rb)],_plot(b,[(ra,"状态 A","#2563eb"),(rb,"状态 B","#f59e0b")],"B / Gs","R / Ω","内部磁阻特性",connect_points=True)
    vals=_numbers(rows,"current","output25","output100"); i,o25,o100=map(list,zip(*vals)); f25=_fit([v/1000 for v in i],o25); f100=_fit([v/1000 for v in i],o100)
    return {"sensitivity25":f25["slope"],"sensitivity100":f100["slope"]},[],_plot(i,[(o25,"25 mV 偏置","#2563eb"),(o100,"100 mV 偏置","#f59e0b")],"I / mA","Vout / mV","无接触电流标定",True)


FORMULAS = {'transfer': ['B({\\rm Gs})=0.31416I({\\rm mA}),\\quad V_{out}=kB+b'],
 'resistance': ['R=\\frac{2U}{I_R}', 'GMR=\\frac{R_{\\max}-R_{\\min}}{R_{\\min}}\\times100\\%'],
 'current_sensor': ['V_{out}=kI+b']}



EXPERIMENT = ConfiguredExperiment(
    experiment_id='gmr',
    config=CONFIG,
    calculator=calculate,
    formulas=FORMULAS,
)
