"""The Extended SDK for Person Directory."""

import asyncio
from collections.abc import Callable, Sequence
from typing import Annotated, TypeAlias

from loguru import logger

from ._models import (
    ActualPerson,
    ActualPersons,
    PersonActualFaces,
    PersonDirectoryFace,
)
from ._typing import RecognitionModel
from .sdk import PersonDirectory

ActualFacesPredicate: TypeAlias = Callable[[PersonDirectoryFace], bool] | None
ActualPersonsPredicate: TypeAlias = Callable[[ActualPerson], bool] | None


class PersonDirectoryExtension(PersonDirectory):
    async def clear_persons(self) -> None:
        """Clear all existing person directories."""
        logger.debug("Clearing all person directories")

        while True:
            persons = (
                await self.get_persons(top=self.GET_PERSONS_RESPONSE_LIMIT)
            ).persons

            if not persons:
                break

            tasks = [self.delete_person(person.person_id) for person in persons]
            await asyncio.gather(*tasks)

    async def clear_faces(
        self,
        person_id: str,
        recognition_model: RecognitionModel = PersonDirectory.DEFAULT_RECOGNITION_MODEL,
        *,
        exclude: set[Annotated[str, "Persisted Face ID to Exclude from Clearing"]]
        | None = None,
    ) -> None:
        """Clear all faces inside a person directory."""
        if exclude is None:
            exclude = set()

        faces = await self.get_person_faces(
            person_id, recognition_model, raise_no_faces=False
        )
        tasks = [
            self.delete_person_face(
                person_id, persisted_face_id, recognition_model, raise_not_found=False
            )
            for persisted_face_id in faces.persisted_face_ids
            if persisted_face_id is not None and persisted_face_id not in exclude
        ]
        await asyncio.gather(*tasks)

    async def get_person_actual_faces(
        self,
        person_id: str,
        recognition_model: RecognitionModel = PersonDirectory.DEFAULT_RECOGNITION_MODEL,
        *,
        where: ActualFacesPredicate = None,
    ) -> PersonActualFaces:
        """Get the complete face object instead of just ids.

        Args:
            person_id: Person ID of the person
            recognition_model: The 'recognitionModel' associated with faces
            where: optional predicate to filter the faces result

        Examples:
            ```python
            person_id = "6614c784-9f6e-4c86-849b-827e6f149d14"

            faces = await pde.get_person_actual_faces(
                person_id, where=lambda f: f.user_data == {"name": "Mohanad"}
            )

            faces = await pde.get_person_actual_faces(
                person_id, where=lambda f: f.user_data == {"class": "elementary1"}
            )

            faces = await pde.get_person_actual_faces(
                person_id, where=lambda f: f.user_data is None
            )

            faces = await pde.get_person_actual_faces(
                person_id,
                where=lambda f: f.persisted_face_id
                in {"50a3cccd-bd59-40e4-9779-4c31c7bf8bbb", ...},
            )
            ```
        """
        face_ids = (
            await super().get_person_faces(person_id, recognition_model)
        ).persisted_face_ids

        tasks = [
            self.get_person_face(person_id, persisted_face_id, recognition_model)
            for persisted_face_id in face_ids
            if persisted_face_id is not None
        ]
        faces: Sequence[PersonDirectoryFace] = await asyncio.gather(*tasks)

        if where is not None:
            faces = list(filter(where, faces))

        return PersonActualFaces(person_id=person_id, faces=faces)

    async def get_actual_persons(
        self,
        start: str | None = None,
        top: int = 10,
        recognition_model: RecognitionModel = PersonDirectory.DEFAULT_RECOGNITION_MODEL,
        *,
        where: ActualPersonsPredicate = None,
    ) -> ActualPersons:
        """Get complete person objects instead of just the ids.

        This includes the following person attributes:
            id, name, user_data, faces

        Examples:
            ```python
            rsp = await pde.get_actual_persons(where=lambda p: p.name == "Mohanad")
            ```
        """
        persons = (await self.get_persons(start, top)).persons

        tasks = [
            self.get_person_actual_faces(person.person_id, recognition_model)
            for person in persons
        ]
        faces = await asyncio.gather(*tasks)

        actual_persons = []
        for person, person_faces in zip(persons, faces, strict=True):
            assert person.person_id == person_faces.person_id
            actual_persons.append(
                ActualPerson(
                    user_data=person.user_data,
                    person_id=person.person_id,
                    name=person.name,
                    faces=person_faces.faces,
                )
            )

        if where:
            actual_persons = filter(where, actual_persons)

        return ActualPersons(persons=list(actual_persons))
