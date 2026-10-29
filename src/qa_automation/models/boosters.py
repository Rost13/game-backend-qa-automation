from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import Field, RootModel

from qa_automation.models.common import ApiModel


class BoosterState(ApiModel):
    type: str
    power_percent: Annotated[int, Field(gt=0)]
    expires_at: datetime
    updated_at: datetime
    source: str


class BoosterStates(RootModel[list[BoosterState]]):
    pass
