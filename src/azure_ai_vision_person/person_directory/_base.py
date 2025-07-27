from collections import namedtuple

from sdk_creator.errors import ApiError

from .._base import ensure_entity_exist, map_error
from .errors import (
    FaceError,
    FaceNotFoundError,
    PersonDirectoryError,
    PersonDirectoryNotFoundError,
)

EntityId = namedtuple("EntityId", ["id", "entity_type"])

ensure_person_exist = ensure_entity_exist(
    param_name="person_id",
    error_class=PersonDirectoryNotFoundError,
    entity_type="Person Directory",
)
ensure_face_exist = ensure_entity_exist(
    param_name="persisted_face_id",
    error_class=FaceNotFoundError,
    entity_type="Person Directory Face",
)


map_face_err = map_error(ApiError, FaceError)
map_persondir_err = map_error(ApiError, PersonDirectoryError)
