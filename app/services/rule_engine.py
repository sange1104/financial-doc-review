import re

import cv2
import numpy as np

from app.schemas.decision import Decision, DocumentReviewResponse
from app.schemas.document import DocumentType
from app.schemas.ocr import OCRResult
from app.schemas.quality import ImageQualityResult
from app.services.ocr_service import extract_bank_account, extract_id_card
from app.services.quality_service import evaluate_quality

ID_NUMBER_PATTERN = re.compile(r"^\d{6}-\d{7}$")
MIN_CONFIDENCE = 0.7
MIN_RAW_TEXT_LENGTH = 10
MIN_IMAGE_PIXELS = 100
BLACK_WHITE_THRESHOLD = 0.95

# 문서 타입 판별용 키워드
ID_CARD_KEYWORDS = ["주민등록증", "운전면허", "여권"]
BANK_KEYWORDS = ["통장", "계좌", "예금", "은행", "Bank"]


def _get_field(ocr: OCRResult, field_name: str):
    for f in ocr.fields:
        if f.field_name == field_name:
            return f
    return None


def _response(doc_type, decision, reason, quality, ocr=None):
    return DocumentReviewResponse(
        document_type=doc_type,
        decision=decision,
        reason=reason,
        quality=quality,
        ocr=ocr or OCRResult(),
    )


# ──────────────────────────────────────────────
# Gate 1: 입력 유효성 검증
# ──────────────────────────────────────────────

def _gate1_input_validity(image_path: str, quality: ImageQualityResult, doc_type: DocumentType) -> DocumentReviewResponse | None:
    """이미지 자체가 유효한지 검증한다."""

    # 이미지 읽기 실패
    img = cv2.imread(image_path)
    if img is None:
        return _response(doc_type, Decision.RETAKE, "Image file could not be read", quality)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # 이미지 크기 최소 기준
    if h < MIN_IMAGE_PIXELS or w < MIN_IMAGE_PIXELS:
        return _response(doc_type, Decision.RETAKE, "Image too small for document recognition", quality)

    # 완전 검은/흰 화면
    black_ratio = np.mean(gray < 10)
    white_ratio = np.mean(gray > 245)
    if black_ratio > BLACK_WHITE_THRESHOLD:
        return _response(doc_type, Decision.RETAKE, "Image is nearly all black", quality)
    if white_ratio > BLACK_WHITE_THRESHOLD:
        return _response(doc_type, Decision.RETAKE, "Image is nearly all white", quality)

    # 품질 불량 (blur, glare, 저해상도)
    if not quality.is_acceptable:
        return _response(doc_type, Decision.RETAKE, _retake_reason(quality), quality)

    return None


# ──────────────────────────────────────────────
# Gate 2: 문서 유형 검증
# ──────────────────────────────────────────────

def _gate2_document_type(ocr: OCRResult, expected_type: DocumentType, quality: ImageQualityResult) -> DocumentReviewResponse | None:
    """OCR 결과에서 문서 유형이 기대와 맞는지 검증한다."""
    raw = ocr.raw_text or ""

    has_id_signals = any(kw in raw for kw in ID_CARD_KEYWORDS)
    has_bank_signals = any(kw in raw for kw in BANK_KEYWORDS)

    if expected_type == DocumentType.ID_CARD and has_bank_signals and not has_id_signals:
        return _response(
            DocumentType.BANK_ACCOUNT_DOC,
            Decision.INVALID_DOC_TYPE,
            "Expected ID card but detected bank account document",
            quality, ocr,
        )

    if expected_type == DocumentType.BANK_ACCOUNT_DOC and has_id_signals and not has_bank_signals:
        return _response(
            DocumentType.ID_CARD,
            Decision.INVALID_DOC_TYPE,
            "Expected bank account document but detected ID card",
            quality, ocr,
        )

    return None


# ──────────────────────────────────────────────
# Gate 3: 필수 정보 존재 검증
# ──────────────────────────────────────────────

def _gate3_required_fields_id(ocr: OCRResult, quality: ImageQualityResult) -> DocumentReviewResponse | None:
    """신분증 필수 필드 존재 여부 + glare 조합 검증."""
    raw_len = len(ocr.raw_text) if ocr.raw_text else 0
    name = _get_field(ocr, "name")
    id_number = _get_field(ocr, "id_number")
    glare = quality.glare_detected

    # OCR 결과가 극단적으로 적으면 retake
    if raw_len < MIN_RAW_TEXT_LENGTH:
        return _response(DocumentType.ID_CARD, Decision.RETAKE,
                         "OCR extracted too little text from image", quality, ocr)

    # glare + 필수 필드 전부 없음 → retake (glare가 원인)
    if not name and not id_number:
        reason = "No required fields (name, id_number) could be extracted"
        if glare:
            reason = "Glare obscured document; " + reason
        return _response(DocumentType.ID_CARD, Decision.RETAKE, reason, quality, ocr)

    # 일부 누락
    review_reasons: list[str] = []
    if not name:
        review_reasons.append("name field not found")
    if not id_number:
        review_reasons.append("id_number field not found")

    # glare + 일부 필드 애매 → review에 glare 언급 추가
    if glare and review_reasons:
        review_reasons.insert(0, "glare detected on document")

    # glare 있지만 필드 다 있으면 → 통과 (pass 가능)

    if review_reasons:
        return _response(DocumentType.ID_CARD, Decision.REVIEW,
                         "; ".join(review_reasons), quality, ocr)

    return None


def _gate3_required_fields_bank(ocr: OCRResult, quality: ImageQualityResult) -> DocumentReviewResponse | None:
    """통장사본 필수 필드 존재 여부 + glare 조합 검증."""
    raw_len = len(ocr.raw_text) if ocr.raw_text else 0
    name = _get_field(ocr, "name")
    account_number = _get_field(ocr, "account_number")
    bank_name = _get_field(ocr, "bank_name")
    glare = quality.glare_detected

    if raw_len < MIN_RAW_TEXT_LENGTH:
        return _response(DocumentType.BANK_ACCOUNT_DOC, Decision.RETAKE,
                         "OCR extracted too little text from image", quality, ocr)

    # glare + 핵심 필드 전부 없음 → retake
    if not name and not account_number:
        reason = "No required fields (name, account_number) could be extracted"
        if glare:
            reason = "Glare obscured document; " + reason
        return _response(DocumentType.BANK_ACCOUNT_DOC, Decision.RETAKE, reason, quality, ocr)

    review_reasons: list[str] = []
    if not name:
        review_reasons.append("name field not found")
    if not account_number:
        review_reasons.append("account_number field not found")
    if not bank_name:
        review_reasons.append("bank_name field not found")

    if glare and review_reasons:
        review_reasons.insert(0, "glare detected on document")

    if review_reasons:
        return _response(DocumentType.BANK_ACCOUNT_DOC, Decision.REVIEW,
                         "; ".join(review_reasons), quality, ocr)

    return None


# ──────────────────────────────────────────────
# Gate 4: 형식 검증 + 최종 확신
# ──────────────────────────────────────────────

def _gate4_validation_id(ocr: OCRResult, quality: ImageQualityResult) -> DocumentReviewResponse | None:
    """신분증 형식 검증 및 confidence 확인."""
    name = _get_field(ocr, "name")
    id_number = _get_field(ocr, "id_number")
    review_reasons: list[str] = []

    if name and name.confidence < MIN_CONFIDENCE:
        review_reasons.append(f"name confidence too low ({name.confidence:.2f})")

    if id_number:
        if not ID_NUMBER_PATTERN.match(id_number.value or ""):
            review_reasons.append(f"id_number format invalid: {id_number.value}")
        elif id_number.confidence < MIN_CONFIDENCE:
            review_reasons.append(f"id_number confidence too low ({id_number.confidence:.2f})")

    if review_reasons:
        return _response(DocumentType.ID_CARD, Decision.REVIEW,
                         "; ".join(review_reasons), quality, ocr)

    return None


def _gate4_validation_bank(ocr: OCRResult, quality: ImageQualityResult) -> DocumentReviewResponse | None:
    """통장사본 형식 검증 및 confidence 확인."""
    name = _get_field(ocr, "name")
    account_number = _get_field(ocr, "account_number")
    bank_name = _get_field(ocr, "bank_name")
    review_reasons: list[str] = []

    if name and name.confidence < MIN_CONFIDENCE:
        review_reasons.append(f"name confidence too low ({name.confidence:.2f})")

    if account_number and account_number.confidence < MIN_CONFIDENCE:
        review_reasons.append(f"account_number confidence too low ({account_number.confidence:.2f})")

    if bank_name and bank_name.confidence < MIN_CONFIDENCE:
        review_reasons.append(f"bank_name confidence too low ({bank_name.confidence:.2f})")

    if review_reasons:
        return _response(DocumentType.BANK_ACCOUNT_DOC, Decision.REVIEW,
                         "; ".join(review_reasons), quality, ocr)

    return None


# ──────────────────────────────────────────────
# 메인 평가 함수
# ──────────────────────────────────────────────

def evaluate_id_card(image_path: str) -> DocumentReviewResponse:
    quality = evaluate_quality(image_path)

    # Gate 1: 입력 유효성
    result = _gate1_input_validity(image_path, quality, DocumentType.ID_CARD)
    if result:
        return result

    # OCR 추출
    ocr = extract_id_card(image_path)

    # Gate 2: 문서 유형
    result = _gate2_document_type(ocr, DocumentType.ID_CARD, quality)
    if result:
        return result

    # Gate 3: 필수 정보
    result = _gate3_required_fields_id(ocr, quality)
    if result:
        return result

    # Gate 4: 형식 검증
    result = _gate4_validation_id(ocr, quality)
    if result:
        return result

    # Pass
    return _response(DocumentType.ID_CARD, Decision.PASS,
                     "All required fields present and valid", quality, ocr)


def evaluate_bank_account(image_path: str) -> DocumentReviewResponse:
    quality = evaluate_quality(image_path)

    # Gate 1: 입력 유효성
    result = _gate1_input_validity(image_path, quality, DocumentType.BANK_ACCOUNT_DOC)
    if result:
        return result

    # OCR 추출
    ocr = extract_bank_account(image_path)

    # Gate 2: 문서 유형
    result = _gate2_document_type(ocr, DocumentType.BANK_ACCOUNT_DOC, quality)
    if result:
        return result

    # Gate 3: 필수 정보
    result = _gate3_required_fields_bank(ocr, quality)
    if result:
        return result

    # Gate 4: 형식 검증
    result = _gate4_validation_bank(ocr, quality)
    if result:
        return result

    # Pass
    return _response(DocumentType.BANK_ACCOUNT_DOC, Decision.PASS,
                     "All required fields present and valid", quality, ocr)


def _retake_reason(quality: ImageQualityResult) -> str:
    reasons = []
    if quality.blur_score is not None and quality.blur_score < 100:
        reasons.append(f"image too blurry (score: {quality.blur_score})")
    if quality.glare_detected:
        reasons.append("glare detected")
    if quality.low_resolution_detected:
        reasons.append("image resolution too low")
    return "; ".join(reasons) if reasons else "image quality unacceptable"
