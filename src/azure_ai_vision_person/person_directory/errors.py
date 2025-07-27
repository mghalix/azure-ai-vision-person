from sdk_creator.toolkit import SdkError


class PersonDirectoryError(SdkError):
    pass


class PersonDirectoryNotFoundError(PersonDirectoryError):
    pass


class FaceError(SdkError):
    pass


class FaceNotFoundError(FaceError):
    pass


class NoFacesFoundError(FaceError):
    pass
