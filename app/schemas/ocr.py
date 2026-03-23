from pydantic import BaseModel


class CharConfidence(BaseModel):
    char: str
    confidence: float


class OCRField(BaseModel):
    field_name: str
    value: str | None = None
    confidence: float = 0.0
    char_confidences: list[CharConfidence] = []


class OCRResult(BaseModel):
    fields: list[OCRField] = []
    raw_text: str | None = None
