"""The Core SDK for Person Directory."""

import json
import uuid
from typing import Any, Final, Self

from loguru import logger
from pydantic import HttpUrl, ValidationError
from sdk_creator.adapter import AsyncRestAdapter
from sdk_creator.errors import ApiRaisedFromStatusError
from sdk_creator.toolkit import join_endpoints, url_to_hostname

from .._base import suppress_logs
from ._base import (
    EntityId,
    ensure_face_exist,
    ensure_person_exist,
    map_face_err,
    map_persondir_err,
)
from ._models import (
    AddFaceResult,
    CreatePersonResult,
    HasFaceUserData,
    ListFaceResult,
    PersonDirectoryCreate,
    PersonDirectoryFace,
    PersonDirectoryPerson,
    PersonDirectoryPersons,
    PersonDirectoryUpdate,
)
from ._typing import DetectionModel, RecognitionModel
from .errors import (
    FaceNotFoundError,
    NoFacesFoundError,
    PersonDirectoryNotFoundError,
)


class PersonDirectory:
    """PersonDirectory is a data structure in public preview made by Azure Face API.

    To perform face recognition operations such as Identify and Find Similar, Face API
    customers need to create an assorted list of Person objects

    It contains unique IDs, optional name strings, and optional user metadata strings
    for each Person identity added to the directory
    """

    SERVICE: Final[str] = "face"
    API_VERSION: Final[str] = "v1.2-preview.1"
    ENDPOINT: Final[str] = "persons"
    DEFAULT_RECOGNITION_MODEL: Final[RecognitionModel] = "recognition_04"
    DEFAULT_DETECTION_MODEL: Final[DetectionModel] = "detection_03"
    GET_PERSONS_RESPONSE_LIMIT: Final[int] = 1000

    _adapter: AsyncRestAdapter

    def __init__(
        self,
        azure_ai_endpoint: str,
        api_key: str,
        api_version: str = "",
    ) -> None:
        """Initialize a PersonDirectory client.

        Args:
            azure_ai_endpoint: Azure AI endpoint URL
            api_key: Azure AI subscription key
            api_version: API version (optional)
        """
        hostname = join_endpoints(url_to_hostname(azure_ai_endpoint), self.SERVICE)
        api_version = api_version or self.API_VERSION

        self._adapter = AsyncRestAdapter(
            hostname=hostname,
            api_version=api_version,
            api_key=api_key,
            scheme="https",
            ssl_verify=True,
            azure_api=True,
            endpoint_prefix=self.ENDPOINT,
        )

    # TODO: make async iterable and remove pagination parameters
    @map_persondir_err
    async def get_persons(
        self, start: str | None = None, top: int = 10
    ) -> PersonDirectoryPersons:
        """List all persons' information in Person Directory.

        Includes personId, name, and userData

        Persons are stored in alphabetical order of personId created in
        Person Directory "Create Person"

        Args:
            start: specifies an ID value from which returned entries will have
                larger IDs based on string comparison. Setting "start" to an empty
                value indicates that entries should be returned starting from the
                first item

            top: determines the maximum number of entries to be returned, with
                a limit of up to 1000 entries per call. To retrieve additional
                entries beyond this limit, specify "start" with the personId of the
                last entry returned in the current call

        Raises:
            PersonDirectoryError: If any error occurred while retrieving the
                Person Directory

        Returns:
            PersonDirectoryPersons: Containing list of persons each has
                person_id, name, user_data
        """
        response = await self._adapter.get("", start=start, top=top)
        return PersonDirectoryPersons.model_validate({"persons": response.data})

    @map_persondir_err
    @ensure_person_exist
    async def get_person(self, person_id: str) -> PersonDirectoryPerson:
        """Retrieve a person's name and userData from Person Directory.

        Args:
            person_id: Person ID of the person

        Raises:
            PersonDirectoryNotFoundError: If the person with person_id does not exist
            PersonDirectoryError: If any error occurred while retrieving the
                Person Directory

        Returns:
            PersonDirectoryPerson: Containing person_id, name, user_data
        """
        self._validate_id_form(EntityId(person_id, "person"))

        response = await self._adapter.get(person_id)
        return PersonDirectoryPerson.model_validate(response.data)

    async def create_person(
        self, name: str, user_data: str | dict
    ) -> CreatePersonResult:
        """Creates a new person in a Person Directory.

        To add face to this person, please call Person Directory "Add Person Face".

        Args:
            name: User defined name, maximum length is 128.
            user_data: Optional user defined data. Length should not exceed 16K.

        Returns:
            An object with the newly created person id.
        """
        # TODO: check for duplicates using the person name
        person = PersonDirectoryCreate(name=name, user_data=user_data)
        response = await self._adapter.post("", data=person.model_dump())
        return CreatePersonResult.model_validate(response.data)

    @map_persondir_err
    async def delete_person(
        self, person_id: str, *, raise_not_found: bool = True
    ) -> bool:
        """Delete an existing person from Person Directory.

        The persistedFaceId(s), userData, person name and face feature(s) in
        the person entry will all be deleted

        Args:
            person_id: UUID of the person to delete
            raise_not_found: Whether to raise exception if person not found

        Raises:
            PersonDirectoryNotFoundError: If person not found and raise_not_found=True
            ValueError: If person_id is not a valid UUID
            PersonDirectoryError: If any error occurred while deleting the
                Person Directory

        Returns:
            True if deleted successfully, False if not found and raise_not_found=False
        """
        self._validate_id_form(EntityId(person_id, "person"))
        try:
            await self._adapter.delete(person_id)
        except ApiRaisedFromStatusError as err:
            if err.status_code != 404:
                logger.error(f"HTTP error deleting person {person_id}: {err}")
                raise

            if raise_not_found:
                logger.error(f"Person not found: {person_id}")
                raise PersonDirectoryNotFoundError(
                    f"Person directory with id {person_id} not found",
                ) from err

            return False
        except Exception as err:
            logger.error(f"Failed to delete person with id: {person_id}\n{err}")
            raise

        return True

    @map_persondir_err
    @ensure_person_exist
    async def update_person(
        self,
        person_id: str,
        name: str | None = None,
        user_data: dict | str | None = None,
        *,
        reserve_user_data_if_unset: bool = True,
    ) -> None:
        """Update name or userData of a person.

        Args:
            person_id: Person ID of the person
            name: User defined name, maximum length is 128
            user_data: Optional user defined data. Length should not exceed 16K
            reserve_user_data_if_unset: By default the api overrides the current
                user_data with null even if on every patch update request even if it
                previously had a value, this param allows the persistance of the
                previous value if it wasn't provided

        Raises:
            PersonDirectoryNotFoundError: If the person_id was not found
            PersonDirectoryError: If any error occurred while updating the
                Person Directory
        """
        if not all((name, user_data)) and reserve_user_data_if_unset:
            person = await self.get_person(person_id)
            name = name or person.name
            user_data = user_data or person.user_data

        data = PersonDirectoryUpdate(name=name, user_data=user_data)

        await self._adapter.patch(person_id, data=data.model_dump(exclude_none=True))
        # TODO: add to sdk-creator library response data model is_success field to be
        # able to return the values as boolean from the endpoints such as this endpoint
        # instead of raising errors immediately

    @map_face_err
    @ensure_person_exist
    @ensure_face_exist
    async def get_person_face(
        self,
        person_id: str,
        persisted_face_id: str,
        recognition_model: RecognitionModel = DEFAULT_RECOGNITION_MODEL,
    ) -> PersonDirectoryFace:
        """Retrieve person face information.

        The persisted person face is specified by its personId, recognitionModel,
        and persistedFaceId.

        Args:
            person_id: Person ID of the person
            persisted_face_id: Face ID of the face
            recognition_model: The 'recognitionModel' associated with faces

        Raises:
            FaceNotFoundError: if the persisted_face_id is not found for a person
            FaceError: If an error occured while retrieving the person face.

        Returns:
            PersonDirectoryFace: Containing the persisted_face_id and face user_data
        """
        endpoint = join_endpoints(
            person_id,
            "recognitionModels",
            recognition_model,
            "persistedfaces",
            persisted_face_id,
        )
        response = await self._adapter.get(endpoint)
        return PersonDirectoryFace.model_validate(response.data)

    async def get_person_faces(
        self,
        person_id: str,
        recognition_model: RecognitionModel = DEFAULT_RECOGNITION_MODEL,
        *,
        raise_no_faces: bool = False,
    ) -> ListFaceResult:
        """Retrieve a person's persisted_face_ids.

        Representing the registered person face feature(s)

        Args:
            person_id: Person ID of the person
            recognition_model: The 'recognitionModel' associated with faces
            raise_no_faces: Raise if no faces are found for a person

        Raises:
            NoFacesFoundError: if the person retrieved by person_id has no registered
                faces and 'raise_no_faces' is set to True

        Returns:
            ListFaceResult:
                Containing the person id with a sequence of persisted_face_ids.
        """
        self._validate_id_form(EntityId(person_id, "person"))
        # implicity ensuring person exist, instead of using 'ensure_person_exist'
        # decorator, since the error might occur from the face endpoint where a person
        # can have no registered faces plus i would need the person reference later
        # on anyway, thus avoiding a redundant call if the decorator was used
        person = await self.get_person(person_id)

        endpoint = join_endpoints(
            person_id, "recognitionModels", recognition_model, "persistedfaces"
        )
        try:
            # TODO: add to sdk_creator no_raise_from_status param in _requests and
            # and others, also add the option to suppress log messages filtered by level
            # then remove suppress_logs, as it won't be needed
            with suppress_logs("sdk_creator.adapter"):
                response = await self._adapter.get(endpoint)
            return ListFaceResult.model_validate(response.data)
        except ApiRaisedFromStatusError as err:
            if err.status_code != 404:
                raise

            if raise_no_faces:
                raise NoFacesFoundError from err

            return ListFaceResult(person_id=person.person_id)

    @map_face_err
    @ensure_person_exist
    @ensure_face_exist
    async def update_person_face(
        self,
        person_id: str,
        persisted_face_id: str,
        user_data: dict | str,
        recognition_model: RecognitionModel = DEFAULT_RECOGNITION_MODEL,
    ) -> None:
        """Update a persisted face's user_data field of a person.

        Args:
            person_id: Person ID of the person
            persisted_face_id: Face ID of the face
            user_data: User-provided data attached to the face. The length limit is 1K
            recognition_model: The 'recognitionModel' associated with faces
        Raises:
            PersonDirectoryNotFoundError: If the person_id was not found
            FaceNotFoundError: if the persisted_face_id is not found for a person
            FaceError: If an error occured while updating the person face.
        """
        endpoint = join_endpoints(
            person_id,
            "recognitionModels",
            recognition_model,
            "persistedfaces",
            persisted_face_id,
        )
        data = HasFaceUserData(user_data=user_data)
        await self._adapter.patch(endpoint, data=data.model_dump())

    @map_face_err
    @ensure_person_exist
    async def add_person_face(
        self,
        person_id: str,
        face_url: str,
        recognition_model: RecognitionModel = DEFAULT_RECOGNITION_MODEL,
        *,
        detection_model: DetectionModel = DEFAULT_DETECTION_MODEL,
        target_face: str | None = None,
        user_data: dict | str | None = None,
    ) -> AddFaceResult:
        """Add a face to a person for face identification or verification.

        Args:
            person_id: UUID of the person
            face_url: URL of the face image
            recognition_model: Recognition model to use
            detection_model: Detection model to use
            target_face: Target face rectangle coordinates

            user_data: User-defined data for the face

        Raises:
            PersonDirectoryNotFoundError: If the person_id was not found
            FaceError: If an error occurred while creating the person face.

        Returns:
            AddFaceResult containing the persisted face ID
        """
        self._validate_id_form(EntityId(person_id, "person"))
        self._validate_url(face_url)

        endpoint = join_endpoints(
            person_id, "recognitionModels", recognition_model, "persistedfaces"
        )

        if isinstance(user_data, dict):
            user_data = json.dumps(user_data)

        response = await self._adapter.post(
            endpoint,
            {"url": face_url},
            detectionModel=detection_model,
            targetFace=target_face,
            userData=user_data,
        )

        return AddFaceResult.model_validate(response.data)

    @map_face_err
    async def delete_person_face(
        self,
        person_id: str,
        persisted_face_id: str,
        recognition_model: RecognitionModel = DEFAULT_RECOGNITION_MODEL,
        *,
        raise_not_found: bool = True,
    ) -> bool:
        """Delete a face from a person in Person Directory.

        Args:
            person_id: Person ID of the person
            persisted_face_id: Face ID of the face
            recognition_model: The 'recognitionModel' associated with faces
            raise_not_found: Whether to raise exception if person not found

        Raises:
            FaceNotFoundError: If the face does not exist and 'raise_not_found' is True
            FaceError: If an error occured while deleting the person face.

        Returns:
            True if deletion is successfull False otherwise
        """
        endpoint = join_endpoints(
            person_id,
            "recognitionModels",
            recognition_model,
            "persistedfaces",
            persisted_face_id,
        )
        self._validate_id_form(
            EntityId(person_id, "person"), EntityId(persisted_face_id, "face")
        )

        try:
            await self._adapter.delete(endpoint)
        except ApiRaisedFromStatusError as err:
            if err.status_code != 404:
                logger.error(f"HTTP error deleting person {person_id}: {err}")
                raise

            if raise_not_found:
                raise FaceNotFoundError(
                    f"face with id {persisted_face_id} not found"
                ) from err

            return False

        except Exception:
            raise

        return True

    def _validate_id_form(self, *entity_ids: EntityId) -> None:
        def id_validator(entity: str, id: str) -> None:
            try:
                uuid.UUID(id, version=4)
            except ValueError as err:
                logger.error(f"Expected {entity}_id to be a UUID string, got {id}")
                raise ValueError(f"Invalid {entity}_id format: {id}") from err

        for id, entity in entity_ids:
            id_validator(entity, id)

    def _validate_url(self, url: str) -> None:
        """Validate that URL is properly formatted."""
        try:
            HttpUrl(url)
        except ValidationError as err:
            raise ValidationError(f"Invalid URL format: {url}") from err

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self._adapter.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._adapter.close()
