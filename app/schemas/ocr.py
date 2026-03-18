from pydantic import BaseModel


class OCRField(BaseModel):
    field_name: str
    value: str | None = None
    confidence: float = 0.0


class OCRResult(BaseModel):
    fields: list[OCRField] = []
    raw_text: str | None = None
