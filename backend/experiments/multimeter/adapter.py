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


def calculate(method, rows, params):
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


FORMULAS = {'voltage': ['\\Delta U_i=U_{{\\rm meas},i}-U_{{\\rm set},i}', 'U_{\\rm meas}=kU_{\\rm set}+b'],
 'current': ['\\Delta I_i=I_{{\\rm meas},i}-I_{{\\rm set},i}', 'I_{\\rm meas}=kI_{\\rm set}+b'],
 'resistance': ['\\Delta R_i=R_{{\\rm meas},i}-R_{{\\rm set},i}', 'R_{\\rm meas}=kR_{\\rm set}+b'],
 'unknown': ['\\varepsilon_r=\\frac{|\\overline{R}_{\\rm meas}-\\overline{R}_{\\rm ref}|}{\\overline{R}_{\\rm '
             'ref}}\\times100\\%'],
 'ac_voltage': ['\\Delta U_i=U_{{\\rm meas},i}-U_{{\\rm set},i}', 'U_{\\rm meas}=kU_{\\rm set}+b'],
 'ac_current': ['\\Delta I_i=I_{{\\rm meas},i}-I_{{\\rm set},i}', 'I_{\\rm meas}=kI_{\\rm set}+b']}



EXPERIMENT = ConfiguredExperiment(
    experiment_id='multimeter',
    config=CONFIG,
    calculator=calculate,
    formulas=FORMULAS,
)
