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
    if method in ("planck", "compensation"):
        vals=[]
        for row in rows:
            try: wl=float(row["wavelength"]); readings=[float(row[k]) for k in ("us1","us2","us3","us4") if row.get(k) not in (None,"")]
            except (ValueError,TypeError,KeyError): continue
            if readings: vals.append((wl,_mean(readings)))
        wl,us=map(np.asarray,zip(*vals)); nu=2.99792458e8/(wl*1e-9); scaled=nu/1e14; f=_fit(scaled,us)
        k=f["slope"]/1e14; e=1.602176634e-19; h=e*k; nu0=-f["intercept"]/k
        result={"h":h,"h_error":abs(h-6.62607015e-34)/6.62607015e-34*100,"nu0":nu0,"work_function":-f["intercept"],"r_squared":f["r_squared"]}
        derived=[{"wavelength":float(a),"frequency":float(b),"us_mean":float(c)} for a,b,c in zip(wl,nu,us)]
        return result,derived,_plot(scaled.tolist(),[(us.tolist(),"截止电压","#2563eb")],"ν / 10¹⁴ Hz","US / V","截止电压与频率",True)
    if method.startswith("iv_"):
        vals=_numbers(rows,"voltage","current"); x,y=map(list,zip(*vals))
        return {"max_current":max(y),"min_current":min(y)},[],None
    vals=[]
    for row in rows:
        try: wl=float(row["wavelength"]); d=float(row["diameter"]); currents=[float(row[k]) for k in ("i1","i2","i3") if row.get(k) not in (None,"")]
        except (ValueError,TypeError,KeyError): continue
        if currents: vals.append((wl,d,_mean(currents)))
    result={}; derived=[]; series=[]
    for wl in (436,546):
        group=[v for v in vals if v[0]==wl]; x=[v[1]**2 for v in group]; y=[v[2] for v in group]; f=_fit(x,y); result[f"r_squared_{wl}"]=f["r_squared"]; series.append((y,f"{wl} nm", "#2563eb" if wl==436 else "#f59e0b")); derived += [{"wavelength":wl,"phi_squared":a,"i_mean":b} for a,b in zip(x,y)]
    x=sorted({v[1]**2 for v in vals})
    return result,derived,_plot(x,series,"Φ² / mm²","Im","饱和光电流与相对光强",True)

def _photoelectric_iv_plot(data: dict) -> str | None:
    series = []
    for method_id, label, color in (
        ("iv_436", "436 nm（Φ=2 mm）", "#2563eb"),
        ("iv_546", "546 nm（Φ=4 mm）", "#f59e0b"),
    ):
        rows = data.get(method_id, {}).get("rows", [])
        values = _numbers(rows, "voltage", "current")
        if values:
            x, y = map(list, zip(*values))
            series.append((x, y, label, color))
    if not series:
        return None
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    for x, y, label, color in series:
        ax.plot(x, y, marker="o", markersize=4.5, color=color,
                linewidth=1.6, label=label, zorder=3)
    ax.set_xlabel("UAK / V")
    ax.set_ylabel(r"I / $10^{-13}$ A")
    ax.set_title("光电管伏安特性（436 nm 与 546 nm）", fontweight="bold")
    ax.grid(alpha=.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")

def _finalize(data, response):
    iv_plot = _photoelectric_iv_plot(data)
    if iv_plot:
        response["plots"].pop("iv_546", None)
        response["plots"]["iv_436"] = iv_plot
    return response



FORMULAS = {'planck': ['\\nu=\\frac{c}{\\lambda},\\quad U_S=k\\nu+b', 'h=ek,\\quad \\nu_0=-\\frac{b}{k},\\quad W=-eb'],
 'iv_436': ['I=I(U_{AK})'],
 'iv_546': ['I=I(U_{AK})'],
 'saturation': ['P_{\\rm rel}\\propto\\Phi^2,\\quad I_m=a\\Phi^2+b'],
 'compensation': ['\\nu=\\frac{c}{\\lambda},\\quad U_S=k\\nu+b', 'h=ek,\\quad \\nu_0=-\\frac{b}{k}']}



EXPERIMENT = ConfiguredExperiment(
    experiment_id='photoelectric',
    config=CONFIG,
    calculator=calculate,
    formulas=FORMULAS,
    public=False,
    legacy=True,
    finalize_result=_finalize,
)
