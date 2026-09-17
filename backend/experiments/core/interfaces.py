"""Stable interface between API infrastructure and experiment modules."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ExperimentAdapter(Protocol):
    id: str
    public: bool
    legacy: bool
    catalogued: bool

    @property
    def config(self) -> Any: ...

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def process(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def build_report(self, payload: dict[str, Any], fmt: str) -> bytes: ...

    def build_record_sheet(self, fmt: str) -> bytes: ...

    def schema(self) -> dict[str, Any]: ...

    def catalog_entry(self) -> dict[str, Any]: ...
