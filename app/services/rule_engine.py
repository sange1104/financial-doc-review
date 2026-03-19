import re

from app.schemas.decision import Decision, DocumentReviewResponse
from app.schemas.document import DocumentType
from app.schemas.ocr import OCRResult
from app.schemas.quality import ImageQualityResult
from app.services.ocr_service import extract_bank_account, extract_id_card
from app.services.quality_service import evaluate_quality

ID_NUMBER_PATTERN = re.compile(r"^\d{6}-\d{7}$")
MIN_CONFIDENCE = 0.7
MIN_RAW_TEXT_LENGTH = 10


def _get_field(ocr: OCRResult, field_name: str):
    for f in ocr.fields:
        if f.field_name == field_name:
            return f
    return None


def _check_retake(quality: ImageQualityResult, doc_type: DocumentType) -> DocumentReviewResponse | None:
    """품질 불량이면 retake 반환, 아니면 None."""
    if not quality.is_acceptable:
        return DocumentReviewResponse(
            document_type=doc_type,
            decision=Decision.RETAKE,
            reason=_retake_reason(quality),
            quality=quality,
            ocr=OCRResult(),
        )
    return None


def _check_empty_ocr(quality: ImageQualityResult, ocr: OCRResult, doc_type: DocumentType) -> DocumentReviewResponse | None:
    """OCR 결과가 극단적으로 적으면 retake 반환."""
    raw_len = len(ocr.raw_text) if ocr.raw_text else 0
    doc_title = _get_field(ocr, "doc_title")
    if raw_len < MIN_RAW_TEXT_LENGTH and not doc_title:
        return DocumentReviewResponse(
            document_type=doc_type,
            decision=Decision.RETAKE,
            reason="OCR extracted too little text from image",
            quality=quality,
            ocr=ocr,
        )
    return None


def evaluate_id_card(image_path: str) -> DocumentReviewResponse:
    quality = evaluate_quality(image_path)

    retake = _check_retake(quality, DocumentType.ID_CARD)
    if retake:
        return retake

    ocr = extract_id_card(image_path)

    empty = _check_empty_ocr(quality, ocr, DocumentType.ID_CARD)
    if empty:
        return empty

    # review 검증: name + id_number
    review_reasons: list[str] = []
    name = _get_field(ocr, "name")
    id_number = _get_field(ocr, "id_number")

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
            document_type=DocumentType.ID_CARD,
            decision=Decision.REVIEW,
            reason="; ".join(review_reasons),
            quality=quality,
            ocr=ocr,
        )

    return DocumentReviewResponse(
        document_type=DocumentType.ID_CARD,
        decision=Decision.PASS,
        reason="All required fields present and valid",
        quality=quality,
        ocr=ocr,
    )


def evaluate_bank_account(image_path: str) -> DocumentReviewResponse:
    quality = evaluate_quality(image_path)

    retake = _check_retake(quality, DocumentType.BANK_ACCOUNT_DOC)
    if retake:
        return retake

    ocr = extract_bank_account(image_path)

    empty = _check_empty_ocr(quality, ocr, DocumentType.BANK_ACCOUNT_DOC)
    if empty:
        return empty

    # review 검증: name + account_number
    review_reasons: list[str] = []
    name = _get_field(ocr, "name")
    account_number = _get_field(ocr, "account_number")

    if not name:
        review_reasons.append("name field not found")
    elif name.confidence < MIN_CONFIDENCE:
        review_reasons.append(f"name confidence too low ({name.confidence:.2f})")

    if not account_number:
        review_reasons.append("account_number field not found")
    elif account_number.confidence < MIN_CONFIDENCE:
        review_reasons.append(f"account_number confidence too low ({account_number.confidence:.2f})")

    if review_reasons:
        return DocumentReviewResponse(
            document_type=DocumentType.BANK_ACCOUNT_DOC,
            decision=Decision.REVIEW,
            reason="; ".join(review_reasons),
            quality=quality,
            ocr=ocr,
        )

    return DocumentReviewResponse(
        document_type=DocumentType.BANK_ACCOUNT_DOC,
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
    if quality.low_resolution_detected:
        reasons.append("image resolution too low")
    return "; ".join(reasons) if reasons else "image quality unacceptable"
