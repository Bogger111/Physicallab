"""Michelson interferometer calculation adapter."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from experiments.core.configured import ConfiguredExperiment
from experiments.core.numerics import mean, numbers, plot, std
from experiments.schema import enrich_config


CONFIG = enrich_config(json.loads(Path(__file__).with_name("config.json").read_text(encoding="utf-8")))


def calculate(method, rows, p):
    if method == "observations":
        vals=numbers(rows,"pattern_code","motion_code")
        return {"observed_rows":len(vals)},[],None
    pos=[v[0] for v in numbers(rows,"position")]
    if len(pos)<10: raise ValueError("逐差法需要 10 个连续位置读数")
    dif=np.diff(pos)
    if not (np.all(dif>0) or np.all(dif<0)): raise ValueError("鼓轮读数必须保持单向变化，避免机械空程差")
    deltas=[abs(pos[i+5]-pos[i]) for i in range(5)]; fringes=p.get("fringes_per_step",50)*5; average=mean(deltas); wavelength=2*average/fringes*1e6
    return {"wavelength":wavelength,"relative_error":abs(wavelength-632.8)/632.8*100,"delta_d_mean":average,"delta_d_std":std(deltas)},[{"group":i+1,"delta_d":v,"wavelength":2*v/fringes*1e6} for i,v in enumerate(deltas)],plot(list(range(1,6)),[(deltas,"逐差位移","#2563eb")],"逐差组","Δd / mm","迈克尔逊逐差结果")


FORMULAS = {
    "wavelength": [r"\Delta d_i=|d_{i+5}-d_i|", r"\lambda=\frac{2\overline{\Delta d}}{250}=\frac{\overline{\Delta d}}{125}"],
}


EXPERIMENT = ConfiguredExperiment(
    experiment_id="michelson",
    config=CONFIG,
    calculator=calculate,
    formulas=FORMULAS,
)
