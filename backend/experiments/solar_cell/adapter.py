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
    if method == "iv":
        vals=_numbers(rows,"voltage","current"); u,i=map(np.asarray,zip(*vals)); power=u*i; idx=int(np.argmax(power)); denom=p.get("uoc",12)*p.get("isc",80)
        result={"p_max":float(power[idx]),"u_opt":float(u[idx]),"i_opt":float(i[idx]),"fill_factor":float(power[idx]/denom) if denom else math.nan}
        derived=[{"voltage":float(a),"current":float(b),"power":float(c)} for a,b,c in zip(u,i,power)]
        fig,ax=plt.subplots(figsize=(7.2,4.5)); ax.plot(u,i,"o-",label="I-V"); ax2=ax.twinx(); ax2.plot(u,power,"s-",color="#f59e0b",label="P-V"); ax.set_xlabel("U / V"); ax.set_ylabel("I / mA"); ax2.set_ylabel("P / mW"); ax.grid(alpha=.25); fig.tight_layout(); buf=io.BytesIO(); fig.savefig(buf,format="png",bbox_inches="tight"); plt.close(fig)
        return result,derived,base64.b64encode(buf.getvalue()).decode()
    if method == "shading":
        vals=_numbers(rows,"condition","isc"); x,y=map(list,zip(*vals)); base=y[0]
        return {"unshaded_isc":base,"minimum_ratio":min(y)/base*100 if base else math.nan},[{"condition":a,"isc":b,"retained_pct":b/base*100 if base else math.nan} for a,b in vals],_plot(x,[(y,"短路电流","#16a34a")],"工况编号","Isc / mA","遮挡影响")
    if method.startswith("charge_"):
        vals=_numbers(rows,"time","voltage","current"); t,u,i=map(np.asarray,zip(*vals)); power=u*i; energy=float(np.trapezoid(power,t)*.06) if len(t)>1 else 0
        return {"energy":energy,"final_voltage":float(u[-1]),"duration":float(t[-1]-t[0])},[{"time":float(a),"voltage":float(b),"current":float(c),"power":float(d)} for a,b,c,d in zip(t,u,i,power)],_plot(t.tolist(),[(power.tolist(),"充电功率","#7c3aed")],"t / min","P / mW","超级电容充电功率",connect_points=True)
    if method == "fan":
        vals=_numbers(rows,"voltage","current"); powers=[u*i for u,i in vals]
        return {"power_before":powers[0],"power_after":powers[1] if len(powers)>1 else math.nan},[],None
    if method == "load_dcdc":
        vals=_numbers(rows,"voltage_before","current_before","voltage_after","current_after")
        u1,i1,u2,i2=vals[0]; p1=u1*i1; p2=u2*i2
        return {"power_before":p1,"power_after":p2,"power_gain":p2-p1},[],None
    vals=_numbers(rows,"input_voltage","input_current","lit_code")
    voltage,current,lit_code=vals[0]
    return {"input_power":voltage*current,"lit_code":lit_code},[],None


FORMULAS = {'iv': ['P_i=U_iI_i,\\quad P_{\\max}=\\max(P_i)', 'FF=\\frac{P_{\\max}}{U_{oc}I_{sc}}'],
 'shading': ['r_i=\\frac{I_{sc,i}}{I_{sc,0}}\\times100\\%'],
 'charge_direct': ['P(t)=U(t)I(t),\\quad E=\\int P(t)\\,dt'],
 'charge_dcdc': ['P(t)=U(t)I(t),\\quad E=\\int P(t)\\,dt'],
 'fan': ['P=UI'],
 'load_dcdc': ['P_1=U_1I_1,\\quad P_2=U_2I_2,\\quad \\Delta P=P_2-P_1'],
 'inverter': ['P_{\\rm in}=U_{\\rm dc}I_{\\rm dc}']}



EXPERIMENT = ConfiguredExperiment(
    experiment_id='solar-cell',
    config=CONFIG,
    calculator=calculate,
    formulas=FORMULAS,
)
