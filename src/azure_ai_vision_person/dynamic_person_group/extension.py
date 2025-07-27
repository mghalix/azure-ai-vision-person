import asyncio

from loguru import logger

from .sdk import DynamicPersonGroup


class DynamicPersonGroupExtension(DynamicPersonGroup):
    async def clear_groups(self) -> None:
        """Clear all existing dynamic person groups."""
        logger.debug("Clearing all dynamic person groups")

        while True:
            groups = (await self.get_groups(top=self.GET_GROUPS_RESPONSE_LIMIT)).groups

            if not groups:
                break

            tasks = [
                self.delete_group(group.dynamic_person_group_id) for group in groups
            ]
            await asyncio.gather(*tasks)
