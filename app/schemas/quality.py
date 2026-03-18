from pydantic import BaseModel


class ImageQualityResult(BaseModel):
    blur_score: float | None = None
    glare_detected: bool | None = None
    low_resolution_detected: bool | None = None
    is_acceptable: bool = True
