import json
import uuid
from collections.abc import Sequence

from pydantic import BaseModel, Field, field_validator
from sdk_creator.toolkit import CamelCaseAliasMixin, SdkModel

from azure_ai_vision_person._models import HasName, HasUserData


class _HasGroupId(SdkModel, CamelCaseAliasMixin):
    dynamic_person_group_id: str = Field(
        pattern=r"^[a-z0-9-_]+$", min_length=1, max_length=64
    )


class _HasAddPersonIds(SdkModel, CamelCaseAliasMixin):
    add_person_ids: Sequence[str] | None = None

    @field_validator("add_person_ids", mode="after")
    @classmethod
    def validate_id_form(cls, value: Sequence[str]) -> Sequence[str]:
        if not value:
            return value

        for id in value:
            uuid.UUID(id, version=4)

        return value


class _HasRemovePersonIds(BaseModel, CamelCaseAliasMixin):
    remove_person_ids: Sequence[str] | None = None

    @field_validator("remove_person_ids", mode="after")
    @classmethod
    def validate_id_form(cls, value: Sequence[str]) -> Sequence[str]:
        if not value:
            return value

        for id in value:
            uuid.UUID(id, version=4)

        return value


class DynamicPersonGroupUpdate(
    _HasAddPersonIds, _HasRemovePersonIds, HasUserData, HasName, CamelCaseAliasMixin
):
    pass


class DynamicPersonGroupModel(_HasGroupId, HasName, HasUserData, CamelCaseAliasMixin):
    @field_validator("user_data", mode="before")
    @classmethod
    def ensure_always_str(cls, value: str | dict | None) -> str | None:
        if isinstance(value, dict):
            value = json.dumps(value)

        return value


class DynamicPersonGroupCreate(DynamicPersonGroupModel):
    add_person_ids: Sequence[str] | None = None


class DynamicPersonGroups(SdkModel):
    groups: Sequence[DynamicPersonGroupModel]


class DynamicPersonGroupPersons(SdkModel, CamelCaseAliasMixin):
    person_ids: Sequence[str] = Field(default_factory=Sequence)


class DynamicPersonGroupReferences(SdkModel):
    dynamic_person_group_ids: Sequence[_HasGroupId]
