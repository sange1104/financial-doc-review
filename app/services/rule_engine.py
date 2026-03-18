import re

from app.schemas.decision import Decision, DocumentReviewResponse
from app.schemas.document import DocumentType
from app.schemas.ocr import OCRResult
from app.schemas.quality import ImageQualityResult

ID_NUMBER_PATTERN = re.compile(r"^\d{6}-\d{7}$")
MIN_CONFIDENCE = 0.7
MIN_RAW_TEXT_LENGTH = 10


def _get_field(ocr: OCRResult, field_name: str):
    for f in ocr.fields:
        if f.field_name == field_name:
            return f
    return None


def decide(quality: ImageQualityResult, ocr: OCRResult) -> DocumentReviewResponse:
    doc_title = _get_field(ocr, "doc_title")
    name = _get_field(ocr, "name")
    id_number = _get_field(ocr, "id_number")

    # --- Step 1: retake (품질 문제) ---
    if not quality.is_acceptable:
        return DocumentReviewResponse(
            document_type=DocumentType.UNKNOWN,
            decision=Decision.RETAKE,
            reason=_retake_reason(quality),
            quality=quality,
            ocr=ocr,
        )

    # OCR 결과가 극단적으로 적으면 retake
    raw_len = len(ocr.raw_text) if ocr.raw_text else 0
    if raw_len < MIN_RAW_TEXT_LENGTH and not doc_title:
        return DocumentReviewResponse(
            document_type=DocumentType.UNKNOWN,
            decision=Decision.RETAKE,
            reason="OCR extracted too little text from image",
            quality=quality,
            ocr=ocr,
        )

    # --- 문서 타입 판별 ---
    doc_type = DocumentType.ID_CARD if doc_title else DocumentType.UNKNOWN

    # --- Step 2: review (정보 불완전 / 신뢰도 낮음) ---
    review_reasons: list[str] = []

    if not name:
        review_reasons.append("name field not found")
    elif name.confidence < MIN_CONFIDENCE:
        review_reasons.append(f"name confidence too low ({name.confidence:.2f})")

    if not id_number:
        review_reasons.append("id_number field not found")
    elif not ID_NUMBER_PATTERN.match(id_number.value or ""):
        review_reasons.append(f"id_number format invalid: {id_number.value}")
    elif id_number.confidence < MIN_CONFIDENCE:
        review_reasons.append(f"id_number confidence too low ({id_number.confidence:.2f})")

    if review_reasons:
        return DocumentReviewResponse(
            document_type=doc_type,
            decision=Decision.REVIEW,
            reason="; ".join(review_reasons),
            quality=quality,
            ocr=ocr,
        )

    # --- Step 3: pass ---
    return DocumentReviewResponse(
        document_type=doc_type,
        decision=Decision.PASS,
        reason="All required fields present and valid",
        quality=quality,
        ocr=ocr,
    )


def _retake_reason(quality: ImageQualityResult) -> str:
    reasons = []
    if quality.blur_score is not None and quality.blur_score < 100:
        reasons.append(f"image too blurry (score: {quality.blur_score})")
    if quality.glare_detected:
        reasons.append("glare detected")
    if quality.crop_detected:
        reasons.append("image appears cropped")
    return "; ".join(reasons) if reasons else "image quality unacceptable"
