from typing import Literal, TypeAlias

RecognitionModel: TypeAlias = Literal[
    "recognition_01", "recognition_02", "recognition_03", "recognition_04"
]
DetectionModel: TypeAlias = Literal["detection_01", "detection_02", "detection_03"]
