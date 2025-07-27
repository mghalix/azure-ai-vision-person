from sdk_creator.errors import ApiError

from .._base import ensure_entity_exist, map_error
from .errors import DynamicPersonGroupError, DynamicPersonGroupNotFoundError

ensure_group_exist = ensure_entity_exist(
    param_name="group_id",
    error_class=DynamicPersonGroupNotFoundError,
    entity_type="Dynamic Person Group",
)
map_group_err = map_error(ApiError, DynamicPersonGroupError)
