import json
from collections.abc import Sequence
from typing import Annotated, Self

from pydantic import BeforeValidator, Field, model_validator
from sdk_creator.toolkit import CamelCaseAliasMixin, SdkModel

from azure_ai_vision_person._models import HasName, HasPersonId, HasUserData


class HasFaceUserData(SdkModel, CamelCaseAliasMixin):
    user_data: Annotated[
        dict | str | None,
        BeforeValidator(lambda v: json.dumps(v) if isinstance(v, dict) else v),
    ] = Field(
        max_length=1024,
        default=None,
        description="User-provided data attached to the face. The length limit is 1K.",
    )


class _PersonDirectoryBase(HasName, HasUserData, CamelCaseAliasMixin):
    pass


class PersonDirectoryCreate(_PersonDirectoryBase):
    pass


class PersonDirectoryUpdate(_PersonDirectoryBase):
    """Same as PersonDirectoryCreate the difference is that they are allowed to be null
    except that at least one of them must be provided.
    """

    @model_validator(mode="after")
    def ensure_at_least_one_set(self) -> Self:
        if not any((self.name, self.user_data)):
            raise ValueError(
                "To update person directory at least one of name or user_data "
                "must be provided"
            )

        return self


class PersonDirectoryPerson(HasPersonId, _PersonDirectoryBase):
    """Person resource for person directory."""


class PersonDirectoryPersons(SdkModel):
    persons: Sequence[PersonDirectoryPerson]


class _HasFace(SdkModel, CamelCaseAliasMixin):
    persisted_face_id: str


class AddFaceResult(_HasFace):
    pass


class PersonDirectoryFace(_HasFace, HasFaceUserData):
    pass


class CreatePersonResult(HasPersonId):
    pass


class ListFaceResult(HasPersonId, CamelCaseAliasMixin):
    persisted_face_ids: Sequence[str | None] = Field(default_factory=list)


# +------------+
# |   Extras   |
# +------------+
class PersonActualFaces(HasPersonId, CamelCaseAliasMixin):
    faces: Sequence[PersonDirectoryFace] = Field(default_factory=list)


class ActualPerson(PersonDirectoryPerson, PersonActualFaces):
    pass


class ActualPersons(SdkModel):
    persons: Sequence[ActualPerson]
