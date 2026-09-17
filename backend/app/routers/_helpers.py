from fastapi import HTTPException

from experiments.core.exceptions import UnknownExperimentError
from experiments.core.registry import registry


def experiment_or_404(experiment_id: str):
    try:
        return registry.get(experiment_id)
    except UnknownExperimentError as exc:
        raise HTTPException(status_code=404, detail="实验配置不存在") from exc
