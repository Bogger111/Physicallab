"""Calculation adapters for the configuration-driven experiment catalogue.

Every adapter accepts the same payload shape and returns the same schema.  The
formulas stay explicit in Python so they can be unit tested and cited verbatim
in the generated report.  Synthetic fixtures validate these paths; complete
real laboratory data has not yet been run end to end.
"""

from __future__ import annotations

import base64
import io
import json
import math
from pathlib import Path
from typing import Callable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


CONFIG_PATH = Path(__file__).with_name("configs.json")
CONFIGS = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
CONFIG_BY_ID = {item["id"]: item for item in CONFIGS}

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.dpi": 130,
    "savefig.dpi": 180,
})


def _numbers(rows: list[dict], *keys: str) -> list[tuple[float, ...]]:
    out = []
    for row in rows:
        try:
            values = tuple(float(row[key]) for key in keys)
        except (KeyError, TypeError, ValueError):
            continue
        if all(math.isfinite(value) for value in values):
            out.append(values)
    return out


def _mean(values) -> float:
    return float(np.mean(values))


def _std(values) -> float:
    return float(np.std(values, ddof=1)) if len(values) > 1 else 0.0


def _fit(x, y) -> dict:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 2 or np.ptp(x) == 0:
        raise ValueError("线性拟合至少需要两个不同的横坐标数据点")
    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    ss_res = float(np.sum((y - fitted) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return {"slope": float(slope), "intercept": float(intercept),
            "r_squared": float(r2), "fitted": fitted.tolist()}


def _plot(x, series: list[tuple[list[float], str, str]], xlabel: str,
          ylabel: str, title: str, fit_lines: bool = False) -> str:
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    for y, label, color in series:
        ax.scatter(x, y, s=30, color=color, edgecolors="white", linewidths=.5,
                   label=label, zorder=3)
        if fit_lines and len(x) >= 2 and np.ptp(x) > 0:
            fit = _fit(x, y)
            xx = np.linspace(min(x), max(x), 100)
            ax.plot(xx, fit["slope"] * xx + fit["intercept"], color=color,
                    linewidth=1.6)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontweight="bold")
    ax.grid(alpha=.25)
    if len(series) > 1 or series[0][1]:
        ax.legend(fontsize=8)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _calibration(rows, unit):
    vals = _numbers(rows, "set", "measured")
    x, y = map(list, zip(*vals))
    f = _fit(x, y)
    errors = [b - a for a, b in vals]
    return ({"slope": f["slope"], "intercept": f["intercept"],
             "r_squared": f["r_squared"], "max_abs_error": max(map(abs, errors))},
            [{"set": a, "measured": b, "error": e} for (a, b), e in zip(vals, errors)],
            _plot(x, [(y, "实验读数", "#2563eb")], f"标准值 / {unit}",
                  f"组装表读数 / {unit}", "校准曲线", True))


def _multimeter(method, rows, params):
    if method in ("voltage", "current", "resistance", "ac_voltage", "ac_current"):
        unit = {"voltage": "mV", "current": "mA", "resistance": "kΩ",
                "ac_voltage": "mV", "ac_current": "mA"}[method]
        return _calibration(rows, unit)
    vals = _numbers(rows, "reference", "measured")
    ref, measured = map(list, zip(*vals))
    mr, mm = _mean(ref), _mean(measured)
    result = {"mean_reference": mr, "mean_measured": mm,
              "relative_error": abs(mm - mr) / abs(mr) * 100 if mr else math.nan}
    return result, [], _plot(ref, [(measured, "未知电阻", "#7c3aed")],
                                  "标准表 / kΩ", "组装表 / kΩ", "未知电阻检验", True)


def _bridge(method, rows, p):
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


def _photoelectric(method, rows, p):
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
        return {"max_current":max(y),"min_current":min(y)},[],_plot(x,[(y,method.replace("iv_","")+" nm","#7c3aed")],"UAK / V","I","光电管伏安特性")
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


def _franck(method, rows, p):
    if method in ("curve", "higher_curve"):
        vals=_numbers(rows,"voltage","current"); x,y=map(list,zip(*vals))
        xlabel = "UKG1 / V" if method == "higher_curve" else "VG2K / V"
        title = "较高激发能级曲线" if method == "higher_curve" else "弗兰克-赫兹特性曲线"
        return {"data_points":len(vals),"current_max":max(y)},[],_plot(x,[(y,"实验曲线","#2563eb")],xlabel,"IP / nA",title)
    if method == "parameter_curve":
        vals=_numbers(rows,"voltage","current_reference","current_variant")
        x,reference,variant=map(list,zip(*vals))
        differences=[abs(a-b) for a,b in zip(reference,variant)]
        return {"data_points":len(vals),"max_difference":max(differences)},[],_plot(
            x,[(reference,"基准参数","#2563eb"),(variant,"改变参数后","#f59e0b")],
            "VG2K / V","IP / nA","工作参数对曲线的影响")
    peaks=[v[0] for v in _numbers(rows,"peak_voltage")]
    if len(peaks)<3: raise ValueError("至少需要 3 个连续峰值电压")
    diffs=[(peaks[i+3]-peaks[i])/3 for i in range(len(peaks)-3)] if len(peaks)>=6 else np.diff(peaks).tolist()
    v0=_mean(diffs)
    return {"v0":v0,"relative_error":abs(v0-4.90)/4.90*100,"spacing_std":_std(diffs)},[{"group":i+1,"delta_u":v} for i,v in enumerate(diffs)],_plot(list(range(1,len(peaks)+1)),[(peaks,"峰位","#dc2626")],"峰序","峰值电压 / V","峰值位置")


def _solar(method, rows, p):
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
        return {"energy":energy,"final_voltage":float(u[-1]),"duration":float(t[-1]-t[0])},[{"time":float(a),"voltage":float(b),"current":float(c),"power":float(d)} for a,b,c,d in zip(t,u,i,power)],_plot(t.tolist(),[(power.tolist(),"充电功率","#7c3aed")],"t / min","P / mW","超级电容充电功率")
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


def _gmr(method, rows, p):
    if method == "transfer":
        vals=_numbers(rows,"excitation","output"); current,out=map(list,zip(*vals)); b=[.31416*v for v in current]; f=_fit(b,out)
        return {"sensitivity":f["slope"],"r_squared":f["r_squared"],"b_max":max(map(abs,b))},[{"field":x,"output":y} for x,y in zip(b,out)],_plot(b,[(out,"磁电转换","#2563eb")],"B / Gs","Vout / mV","GMR 磁电转换")
    if method == "resistance":
        vals=_numbers(rows,"excitation","ir_a","ir_b"); supply=p.get("supply",2); b=[.31416*v[0] for v in vals]; ra=[2*supply/(v[1]/1000) for v in vals]; rb=[2*supply/(v[2]/1000) for v in vals]
        g=lambda r:(max(r)-min(r))/min(r)*100
        ga,gb=g(ra),g(rb)
        return {"gmr_a":ga,"gmr_b":gb,"sensitive_state":1 if ga>=gb else 2},[{"field":x,"ra":a,"rb":bb} for x,a,bb in zip(b,ra,rb)],_plot(b,[(ra,"状态 A","#2563eb"),(rb,"状态 B","#f59e0b")],"B / Gs","R / Ω","内部磁阻特性")
    vals=_numbers(rows,"current","output25","output100"); i,o25,o100=map(list,zip(*vals)); f25=_fit([v/1000 for v in i],o25); f100=_fit([v/1000 for v in i],o100)
    return {"sensitivity25":f25["slope"],"sensitivity100":f100["slope"]},[],_plot(i,[(o25,"25 mV 偏置","#2563eb"),(o100,"100 mV 偏置","#f59e0b")],"I / mA","Vout / mV","无接触电流标定",True)


def _nmr(method, rows, p):
    if method == "waveform":
        vals=_numbers(rows,"sample_code","tail_count","t1","t2")
        return {"observed_rows":len(vals),
                "max_symmetry_error":max(abs(t1-t2) for _,_,t1,t2 in vals)},[],None
    vals=_numbers(rows,"frequency","field"); nu,b=map(list,zip(*vals)); f=_fit(b,nu); gamma=f["slope"]*1000; g=gamma/7.6225914; ref=5.5857 if method=="hydrogen" else 5.2567
    if method == "pure_water": ref=5.5857
    return {"gamma":gamma,"g_factor":g,"relative_error":abs(g-ref)/ref*100,"r_squared":f["r_squared"]},[],_plot(b,[(nu,r"$^1$H" if method=="hydrogen" else r"$^{19}$F","#2563eb")],"B0 / mT","ν / MHz","核磁共振线性拟合",True)


def _viscosity(method, rows, p):
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
                    "d / mm","Re","球径与雷诺数")
    vals=[]
    for row in rows:
        try: temp=float(row["temperature"]); ts=[float(row[k]) for k in ("t1","t2","t3","t4") if row.get(k) not in (None,"")]
        except (ValueError,TypeError,KeyError): continue
        if ts: vals.append((temp,_mean(ts)))
    L=p.get("distance",20)/100; d=p.get("diameter",1.5)/1000; rho=p.get("rho_ball",7800); rho0=p.get("rho_oil",950); D=p.get("tube_diameter",2)/100; g=p.get("g",9.794); derived=[]
    for temp,t in vals:
        v=L/t; eta=g*d*d*(rho-rho0)/(18*v*(1+2.4*d/D)); re=rho0*v*d/eta; corrected=eta if re<.1 else eta*(1-3*re/16) if re<1 else eta
        derived.append({"temperature":temp,"t_mean":t,"velocity":v,"eta":eta,"re":re,"eta_corrected":corrected})
    return {"eta_20":derived[0]["eta_corrected"],"re_min":min(d["re"] for d in derived),"re_max":max(d["re"] for d in derived)},derived,_plot([d["temperature"] for d in derived],[([d["eta_corrected"] for d in derived],"η′","#dc2626")],"T / °C","η′ / Pa·s","粘滞系数与温度")


def _surface(method, rows, p):
    if method == "calibration":
        vals=_numbers(rows,"mass","u_up","u_down"); m,up,down=map(list,zip(*vals)); force=[v/1000*p.get("g",9.79338) for v in m]; mean_u=[(a+b)/2 for a,b in zip(up,down)]; f=_fit(force,mean_u)
        return {"sensitivity":f["slope"],"r_squared":f["r_squared"],"hysteresis":max(abs(a-b) for a,b in zip(up,down))},[],_plot(force,[(mean_u,"平均电压","#2563eb")],"F / N","U / mV","力敏传感器定标",True)
    if method in ("pull_off", "salt_pull_off"):
        vals=_numbers(rows,"u1","u2"); k=p.get("sensitivity",1000); circumference=math.pi*(p.get("d1",3.31)+p.get("d2",3.496))/100; sigmas=[abs(a-b)/k/circumference for a,b in vals]
        return {"sigma":_mean(sigmas),"sigma_std":_std(sigmas)},[{"delta_u":abs(a-b),"sigma":s} for (a,b),s in zip(vals,sigmas)],_plot(list(range(1,len(sigmas)+1)),[(sigmas,"拉脱法","#7c3aed")],"测量序号",r"σ / N·m$^{-1}$","拉脱法重复测量")
    vals=_numbers(rows,"y1","y2","x1","x2"); hs=[abs(a-b) for a,b,_,_ in vals]; ds=[abs(c-d) for _,_,c,d in vals]; h=_mean(hs); d=_mean(ds); sigma=.25*p.get("density",998)*p.get("g",9.79338)*(d/1000)*(h/1000+d/6000)
    return {"sigma":sigma,"height":h,"diameter":d},[{"height":hh,"diameter":dd} for hh,dd in zip(hs,ds)],_plot(list(range(1,len(hs)+1)),[(hs,"液柱高","#2563eb"),(ds,"内径","#f59e0b")],"测量序号","mm","毛细管读数")


def _thermal(method, rows, p):
    if method == "geometry":
        vals=_numbers(rows,"dc","hc","db","hb"); cols=list(zip(*vals)); keys=("dc_mean","hc_mean","db_mean","hb_mean")
        return {k:_mean(v) for k,v in zip(keys,cols)},[],None
    if method == "heating":
        vals=_numbers(rows,"time","ta","tc"); t,ta,tc=map(list,zip(*vals)); last=min(5,len(vals)); t1=_mean(ta[-last:]); t2=_mean(tc[-last:]); drift=max(max(ta[-last:])-min(ta[-last:]),max(tc[-last:])-min(tc[-last:]))
        return {"t1":t1,"t2":t2,"steady_drift":drift},[],_plot(t,[(ta,"上盘 TA","#dc2626"),(tc,"下盘 TC","#2563eb")],"t / min","T / °C","升温与稳态过程")
    vals=_numbers(rows,"time","temperature"); t,temp=map(np.asarray,zip(*vals)); target=p.get("t2",35); order=np.argsort(np.abs(temp-target))[:min(10,len(temp))]; f=_fit(t[order],temp[order]); rate=abs(f["slope"]); m=p.get("mass",500)/1000; c=p.get("specific_heat",394); rc=p.get("dc",100)/2000; hc=p.get("hc",10)/1000; rb=p.get("db",100)/2000; hb=p.get("hb",8)/1000; dt=p.get("t1",50)-p.get("t2",35); xi=(2*rc+hc)/(2*rc+2*hc); lam=m*c*rate*hb/(math.pi*rb*rb*dt)*xi
    return {"cooling_rate":rate,"lambda":lam,"geometry_factor":xi,"r_squared":f["r_squared"]},[],_plot(t.tolist(),[(temp.tolist(),"冷却曲线","#2563eb")],"t / s","TC / °C","自然冷却曲线")


def _michelson(method, rows, p):
    if method == "observations":
        vals=_numbers(rows,"pattern_code","motion_code")
        return {"observed_rows":len(vals)},[],None
    pos=[v[0] for v in _numbers(rows,"position")]
    if len(pos)<10: raise ValueError("逐差法需要 10 个连续位置读数")
    dif=np.diff(pos)
    if not (np.all(dif>0) or np.all(dif<0)): raise ValueError("鼓轮读数必须保持单向变化，避免机械空程差")
    deltas=[abs(pos[i+5]-pos[i]) for i in range(5)]; fringes=p.get("fringes_per_step",50)*5; mean=_mean(deltas); wavelength=2*mean/fringes*1e6
    return {"wavelength":wavelength,"relative_error":abs(wavelength-632.8)/632.8*100,"delta_d_mean":mean,"delta_d_std":_std(deltas)},[{"group":i+1,"delta_d":v,"wavelength":2*v/fringes*1e6} for i,v in enumerate(deltas)],_plot(list(range(1,6)),[(deltas,"逐差位移","#2563eb")],"逐差组","Δd / mm","迈克尔逊逐差结果")


HANDLERS: dict[str, Callable] = {
    "multimeter": _multimeter, "bridge": _bridge, "photoelectric": _photoelectric,
    "franck-hertz": _franck, "solar-cell": _solar, "gmr": _gmr, "nmr": _nmr,
    "viscosity": _viscosity, "surface-tension": _surface,
    "thermal-conductivity": _thermal, "michelson": _michelson,
}


def process_experiment(experiment_id: str, data: dict) -> dict:
    config = CONFIG_BY_ID.get(experiment_id)
    if not config: return {"status":"validation_error","errors":["未知实验"],"results":{},"plots":{}}
    handler = HANDLERS[experiment_id]; results={}; plots={}; derived={}; errors=[]
    for method in config["methods"]:
        payload=data.get(method["id"],{}); rows=payload.get("rows",[]); params=payload.get("params",{})
        if not rows or not any(any(value not in (None, "") for value in row.values()) for row in rows):
            if method.get("required"): errors.append(f"{method['name']}：未提供数据")
            continue
        try:
            result, detail, plot = handler(method["id"], rows, params)
            results[method["id"]]=result; derived[method["id"]]=detail
            if plot: plots[method["id"]]=plot
        except Exception as exc:
            errors.append(f"{method['name']}：{exc}")
    status="success" if results else "validation_error"
    return {"status":status,"results":results,"plots":plots,"derived":derived,"errors":errors}
