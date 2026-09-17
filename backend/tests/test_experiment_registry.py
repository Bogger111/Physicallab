"""Architecture regressions for the explicit experiment registry."""

import pytest

from experiments.core.exceptions import UnknownExperimentError
from experiments.core.registry import (
    PUBLIC_EXPERIMENT_IDS,
    ExperimentRegistry,
    registry,
)
from tests.test_public_experiment_usability import load_fixture


EXPECTED_MODULES = {
    "polarization": "experiments.polarization.experiment",
    "sound-light": "experiments.soundlight.experiment",
    "multimeter": "experiments.multimeter.adapter",
    "bridge": "experiments.bridge.adapter",
    "solar-cell": "experiments.solar_cell.adapter",
    "gmr": "experiments.gmr.adapter",
    "nmr": "experiments.nmr.adapter",
    "viscosity": "experiments.viscosity.adapter",
    "surface-tension": "experiments.surface_tension.adapter",
    "thermal-conductivity": "experiments.thermal_conductivity.adapter",
    "michelson": "experiments.michelson.adapter",
    "photoelectric-franck-hertz": "experiments.photoelectric_franck_hertz.adapter",
}


def _implementation_module(experiment) -> str:
    calculator = getattr(experiment, "calculator", None)
    return calculator.__module__ if calculator else type(experiment).__module__


def test_every_public_id_has_one_isolated_registry_entry():
    assert tuple(item.id for item in registry.public()) == PUBLIC_EXPERIMENT_IDS
    assert set(PUBLIC_EXPERIMENT_IDS) == set(EXPECTED_MODULES)
    for experiment_id, expected_module in EXPECTED_MODULES.items():
        experiment = registry.get(experiment_id)
        assert _implementation_module(experiment) == expected_module
        assert "experiments.general" not in expected_module


def test_registry_rejects_duplicate_ids():
    experiment = registry.get("michelson")
    with pytest.raises(ValueError, match="重复实验 ID"):
        ExperimentRegistry((experiment, experiment))


def test_unknown_id_has_an_explicit_error():
    with pytest.raises(UnknownExperimentError, match="not-registered"):
        registry.get("not-registered")


@pytest.mark.parametrize("experiment_id", PUBLIC_EXPERIMENT_IDS)
def test_every_public_experiment_loads_config_and_schema(experiment_id):
    experiment = registry.get(experiment_id)
    assert experiment.config
    schema = experiment.schema()
    assert schema["definition"]["id"] == experiment_id
    assert schema["definition"]["methods"]


@pytest.mark.parametrize("experiment_id", PUBLIC_EXPERIMENT_IDS)
def test_every_public_typical_fixture_processes_through_registry(experiment_id):
    fixture = load_fixture(experiment_id, "typical")
    experiment = registry.get(experiment_id)
    if fixture["kind"] == "polarization":
        responses = [experiment.process({**fixture.get("setup", {}), **fixture["data"]})]
    elif fixture["kind"] == "sound-light":
        responses = [experiment.process({"method": method_id, **payload})
                     for method_id, payload in fixture["data"].items()]
    else:
        responses = [experiment.process(fixture["data"])]
    assert responses
    assert all(response["status"] == "success" for response in responses)
    assert all(response.get("results") for response in responses)
