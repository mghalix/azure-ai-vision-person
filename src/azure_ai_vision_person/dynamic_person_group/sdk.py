"""The Core SDK for Dynamic Person Group."""

from collections.abc import Sequence
from typing import Final

from sdk_creator.adapter import AsyncRestAdapter, join_endpoints
from sdk_creator.toolkit import url_to_hostname

from ._base import ensure_group_exist, map_group_err
from .models import (
    DynamicPersonGroupCreate,
    DynamicPersonGroupModel,
    DynamicPersonGroupPersons,
    DynamicPersonGroupReferences,
    DynamicPersonGroups,
    DynamicPersonGroupUpdate,
)


class DynamicPersonGroup:
    SERVICE: Final[str] = "face"
    ENDPOINT: Final[str] = "dynamicpersongroups"
    API_VERSION: Final[str] = "v1.2-preview.1"
    GET_GROUPS_RESPONSE_LIMIT: Final[int] = 1000

    _adapter: AsyncRestAdapter

    def __init__(
        self,
        azure_ai_endpoint: str,
        api_key: str,
        api_version: str = "",
    ) -> None:
        """Initialize dynamic person group."""
        hostname = join_endpoints(url_to_hostname(azure_ai_endpoint), self.SERVICE)
        api_version = api_version or self.API_VERSION

        self._adapter = AsyncRestAdapter(
            hostname=hostname,
            api_key=api_key,
            api_version=api_version,
            azure_api=True,
            endpoint_prefix=self.ENDPOINT,
        )

    @map_group_err
    async def get_groups(
        self, start: str | None = None, top: int = 10
    ) -> DynamicPersonGroups:
        """List all existing Dynamic Person Groups.

        Dynamic Person Groups are stored in alphabetical order of
        dynamic_person_group_id.

        Args:
            start: Specifies an ID value from which returned entries will have larger
                IDs based on string comparison. Setting "start" to an empty value
                indicates that entries should be returned starting from the first item
            top: Determines the maximum number of entries to be returned, with a limit
                of up to 1000 entries per call. To retrieve additional entries beyond
                this limit, specify "start" with the personId of the last entry
                returned in the current call

        Raises:
            DynamicPersonGroupError: If the request failed for any reason

        Returns:
            DynamicPersonGroups:
                Containing a list of groups each has a dynamic_person_group_id
                along with name and user_data.
        """
        response = await self._adapter.get("", start=start, top=top)
        return DynamicPersonGroups.model_validate({"groups": response.data})

    @map_group_err
    @ensure_group_exist
    async def get_group(
        self,
        group_id: str,
        start: str | None = None,
        top: int = 10,
    ) -> DynamicPersonGroupModel:
        """List all existing Dynamic Person Groups.

        by dynamic_person_group_id along with name and user_data.

        """
        response = await self._adapter.get(group_id, start=start, top=top)
        return DynamicPersonGroupModel.model_validate(response.data)

    # FIXME: NOT WORKING
    @map_group_err
    async def create_group(
        self,
        id: str,
        name: str,
        user_data: str | dict | None = None,
        person_ids: Sequence[str] | None = None,
    ) -> None:
        """Creates a new Dynamic Person Group."""
        dpg = DynamicPersonGroupCreate(
            dynamic_person_group_id=id,
            name=name,
            user_data=user_data,
            add_person_ids=person_ids,
        )
        data = dpg.model_dump(exclude_none=True)

        await self._adapter.post("", data=data)

    @map_group_err
    @ensure_group_exist
    async def delete_group(self, group_id: str) -> None:
        await self._adapter.delete(group_id)

    @map_group_err
    @ensure_group_exist
    async def get_group_persons(
        self,
        group_id: str,
        *,
        start: str | None = None,
        top: int | None = None,
    ) -> DynamicPersonGroupPersons:
        endpoint = join_endpoints(group_id, "persons")
        response = await self._adapter.get(endpoint, start=start, top=top)
        return DynamicPersonGroupPersons.model_validate(response.data)

    async def get_group_references(
        self, person_id: str, *, start: str | None = None, top: int | None = None
    ) -> DynamicPersonGroupReferences:
        endpoint = join_endpoints(person_id, "dynamicPersonGroupReferences")
        response = await self._adapter.get(endpoint, start=start, top=top)
        return DynamicPersonGroupReferences.model_validate(response.data)

    async def update_group(
        self,
        group_id: str,
        name: str | None = None,
        user_data: dict | str | None = None,
        person_ids_add: Sequence[str] | None = None,
        person_ids_remove: Sequence[str] | None = None,
    ) -> None:
        """Update the a Dynamic Person Group and manage its members.

        Update the name or user_data of an existing Dynamic Person Group.
        Manage its members by adding or removing persons.

        Args:
            group_id: ID of the dynamic person group
            person_ids_add: Array of personIds created by Person Directory
                "Create Person" to be added
            person_ids_remove: Array of personIds created by Person Directory
                "Create Person" to be removed
            name: User defined name, maximum length is 128
            user_data: Optional user defined data. Length should not exceed 16K
        """
        data = DynamicPersonGroupUpdate(
            name=name,
            user_data=user_data,
            remove_person_ids=person_ids_remove,
            add_person_ids=person_ids_add,
        )
        await self._adapter.patch(group_id, data.model_dump(exclude_none=True))
