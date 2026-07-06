import importlib
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator

from ampel.contrib.hu.t2.HopskotchAdapter import HopskotchAdapter
from ampel.struct.UnitResult import UnitResult
from ampel.util.mappings import get_by_path


def _get_model(value: Any) -> type[BaseModel]:
    if isinstance(value, type) and issubclass(value, BaseModel):
        return value
    if isinstance(value, str):
        mod, attr = value.rsplit(".", 1)
        model = getattr(importlib.import_module(mod), attr)
        if isinstance(model, type) and issubclass(model, BaseModel):
            return model
        raise TypeError(f"{value} is not a BaseModel subclass")
    raise TypeError("model must be a BaseModel subclass a fully-qualified name")


class ConditionalHopskotchAdapter(HopskotchAdapter):
    conditional_path: int | str | list[int | str]
    model: Annotated[type[BaseModel], BeforeValidator(_get_model)]

    def handle(self, ur: UnitResult) -> UnitResult:
        assert isinstance(ur.body, dict)
        return super().handle(ur) if get_by_path(ur.body, self.conditional_path) else ur
