class UnknownExperimentError(LookupError):
    """Raised when no registered experiment has the requested ID."""


class ExperimentInputError(ValueError):
    """Raised when an API-compatible payload is missing required structure."""
