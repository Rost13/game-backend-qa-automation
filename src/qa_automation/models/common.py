from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class SuccessEnvelope(ApiModel):
    ok: Literal[True]
    data: object


class ErrorEnvelope(ApiModel):
    ok: Literal[False]
    error_description: str
