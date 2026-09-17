"""Experiment catalogue, config, schema, validation, and processing routes."""

from fastapi import APIRouter, HTTPException

from app.models import GenericExperimentRequest, ProcessRequest, SoundLightProcessRequest
from app.routers._helpers import experiment_or_404
from experiments.core.exceptions import ExperimentInputError
from experiments.core.registry import registry


router = APIRouter()


@router.get("/api/experiments")
async def list_experiments(include_legacy: bool = False):
    return {"experiments": registry.catalogue(include_legacy=include_legacy)}


@router.get("/api/experiments/polarization/config")
async def get_polarization_config():
    return registry.get("polarization").config


@router.get("/api/experiments/sound-light/config")
async def get_soundlight_config():
    return registry.get("sound-light").config


@router.get("/api/experiments/{experiment_id}/config")
async def get_experiment_config(experiment_id: str):
    return experiment_or_404(experiment_id).config


@router.get("/api/experiments/{experiment_id}/schema")
async def get_experiment_schema(experiment_id: str):
    return experiment_or_404(experiment_id).schema()


@router.post("/api/experiments/polarization/process")
async def process_polarization(req: ProcessRequest):
    try:
        return registry.get("polarization").process(req.model_dump())
    except ExperimentInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/experiments/sound-light/process")
async def process_soundlight(req: SoundLightProcessRequest):
    return registry.get("sound-light").process(req.model_dump())


@router.post("/api/experiments/{experiment_id}/process")
async def process_experiment(experiment_id: str, req: GenericExperimentRequest):
    return experiment_or_404(experiment_id).process(req.data)


@router.post("/api/experiments/polarization/validate")
async def validate_polarization(req: ProcessRequest):
    return registry.get("polarization").validate(req.model_dump())


@router.post("/api/experiments/sound-light/validate")
async def validate_soundlight(req: SoundLightProcessRequest):
    try:
        return registry.get("sound-light").validate(req.model_dump())
    except ExperimentInputError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/experiments/{experiment_id}/validate")
async def validate_experiment(experiment_id: str, req: GenericExperimentRequest):
    return experiment_or_404(experiment_id).validate(req.data)
