from enum import Enum

from pydantic import BaseModel

from app.schemas.document import DocumentType
from app.schemas.ocr import OCRResult
from app.schemas.quality import ImageQualityResult


class Decision(str, Enum):
    PASS = "pass"
    RETAKE = "retake"
    REVIEW = "review"


class DocumentReviewResponse(BaseModel):
    document_type: DocumentType
    decision: Decision
    reason: str
    quality: ImageQualityResult
    ocr: OCRResult
