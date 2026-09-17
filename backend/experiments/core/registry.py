"""Explicit registry for all public and compatibility experiment adapters."""

from __future__ import annotations

from collections.abc import Iterable

from experiments.core.exceptions import UnknownExperimentError
from experiments.core.interfaces import ExperimentAdapter
from experiments.polarization import EXPERIMENT as POLARIZATION
from experiments.soundlight import EXPERIMENT as SOUND_LIGHT
from experiments.multimeter import EXPERIMENT as MULTIMETER
from experiments.bridge import EXPERIMENT as BRIDGE
from experiments.photoelectric import EXPERIMENT as PHOTOELECTRIC
from experiments.franck_hertz import EXPERIMENT as FRANCK_HERTZ
from experiments.solar_cell import EXPERIMENT as SOLAR_CELL
from experiments.gmr import EXPERIMENT as GMR
from experiments.nmr import EXPERIMENT as NMR
from experiments.viscosity import EXPERIMENT as VISCOSITY
from experiments.surface_tension import EXPERIMENT as SURFACE_TENSION
from experiments.thermal_conductivity import EXPERIMENT as THERMAL_CONDUCTIVITY
from experiments.michelson import EXPERIMENT as MICHELSON
from experiments.photoelectric_franck_hertz import EXPERIMENT as PHOTOELECTRIC_FRANCK_HERTZ


PUBLIC_EXPERIMENT_IDS = (
    "polarization",
    "sound-light",
    "multimeter",
    "bridge",
    "solar-cell",
    "gmr",
    "nmr",
    "viscosity",
    "surface-tension",
    "thermal-conductivity",
    "michelson",
    "photoelectric-franck-hertz",
)

CATALOGUE_WITH_LEGACY_IDS = (
    "polarization",
    "sound-light",
    "multimeter",
    "bridge",
    "photoelectric",
    "solar-cell",
    "gmr",
    "nmr",
    "viscosity",
    "surface-tension",
    "thermal-conductivity",
    "michelson",
    "photoelectric-franck-hertz",
)


class ExperimentRegistry:
    def __init__(self, experiments: Iterable[ExperimentAdapter]) -> None:
        self._experiments: dict[str, ExperimentAdapter] = {}
        for experiment in experiments:
            if experiment.id in self._experiments:
                raise ValueError(f"重复实验 ID：{experiment.id}")
            self._experiments[experiment.id] = experiment

    def get(self, experiment_id: str) -> ExperimentAdapter:
        try:
            return self._experiments[experiment_id]
        except KeyError as exc:
            raise UnknownExperimentError(f"实验配置不存在：{experiment_id}") from exc

    def all(self) -> tuple[ExperimentAdapter, ...]:
        return tuple(self._experiments.values())

    def public(self) -> tuple[ExperimentAdapter, ...]:
        return tuple(self.get(experiment_id) for experiment_id in PUBLIC_EXPERIMENT_IDS)

    def catalogue(self, include_legacy: bool = False) -> list[dict]:
        ids = CATALOGUE_WITH_LEGACY_IDS if include_legacy else PUBLIC_EXPERIMENT_IDS
        return [self.get(experiment_id).catalog_entry() for experiment_id in ids]


registry = ExperimentRegistry((
    POLARIZATION,
    SOUND_LIGHT,
    MULTIMETER,
    BRIDGE,
    PHOTOELECTRIC,
    FRANCK_HERTZ,
    SOLAR_CELL,
    GMR,
    NMR,
    VISCOSITY,
    SURFACE_TENSION,
    THERMAL_CONDUCTIVITY,
    MICHELSON,
    PHOTOELECTRIC_FRANCK_HERTZ,
))
