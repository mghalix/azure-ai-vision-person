from sdk_creator.toolkit import SdkError


class DynamicPersonGroupError(SdkError):
    pass


class DynamicPersonGroupNotFoundError(DynamicPersonGroupError):
    pass
