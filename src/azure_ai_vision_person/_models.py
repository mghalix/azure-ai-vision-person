"""Shared Models."""

import json
from typing import Annotated, TypeVar

from pydantic import BaseModel, BeforeValidator, Field
from sdk_creator.toolkit import CamelCaseAliasMixin, SdkModel

T = TypeVar("T", bound=BaseModel)


class HasPersonId(SdkModel, CamelCaseAliasMixin):
    person_id: Annotated[str, "Person ID of the person."]


class HasName(SdkModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="User defined name, maximum length is 128.",
    )


class HasUserData(SdkModel):
    user_data: Annotated[
        str | dict | None,
        BeforeValidator(lambda v: json.dumps(v) if isinstance(v, dict) else v),
    ] = Field(
        default=None,
        max_length=16384,
        description="Optional user defined data. Length should not exceed 16K.",
    )
