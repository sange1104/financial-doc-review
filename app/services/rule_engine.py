import re

import cv2
import numpy as np

from app.schemas.decision import Decision, DocumentReviewResponse
from app.schemas.document import DocumentType
from app.schemas.ocr import OCRField, OCRResult
from app.schemas.quality import ImageQualityResult
from app.services.ocr_service import extract_bank_account, extract_id_card
from app.services.quality_service import BLUR_THRESHOLD, evaluate_quality

ID_NUMBER_PATTERN = re.compile(r"^\d{6}-\d{7}$")
CRITICAL_CONFIDENCE = 0.7   # 핵심 필드 (id_number, account_number)
NAME_CONFIDENCE = 0.6       # 이름 (heuristic 추출이라 기준 낮춤)
SECONDARY_CONFIDENCE = 0.5  # 보조 필드 (bank_name)
CHAR_CONFIDENCE = 0.5       # 글자별 최소 confidence (이하이면 해당 글자 review)
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
    """OCR 자체가 무의미한 경우만 retake로 보낸다.
    blur, 저해상도, glare는 기록만 하고 OCR을 진행시킨다."""

    # 이미지 읽기 실패
    img = cv2.imread(image_path)
    if img is None:
        return _response(doc_type, Decision.RETAKE, "Image file could not be read", quality)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # 이미지 크기 최소 기준 (OCR 자체가 불가능한 수준)
    if h < MIN_IMAGE_PIXELS or w < MIN_IMAGE_PIXELS:
        return _response(doc_type, Decision.RETAKE, "Image too small for document recognition", quality)

    # 완전 검은/흰 화면 (문서가 없음)
    black_ratio = np.mean(gray < 10)
    white_ratio = np.mean(gray > 245)
    if black_ratio > BLACK_WHITE_THRESHOLD:
        return _response(doc_type, Decision.RETAKE, "Image is nearly all black", quality)
    if white_ratio > BLACK_WHITE_THRESHOLD:
        return _response(doc_type, Decision.RETAKE, "Image is nearly all white", quality)

    # blur, 저해상도, glare → quality에 기록됨, OCR 진행
    return None


# ──────────────────────────────────────────────
# Gate 2: 문서 유형 검증
# ──────────────────────────────────────────────

def _gate2_document_type(ocr: OCRResult, expected_type: DocumentType, quality: ImageQualityResult, image_path: str, on_progress=None) -> DocumentReviewResponse | None:
    """OCR 결과에서 문서 유형이 기대와 맞는지 검증한다.
    애매한 경우 VLM을 호출한다."""
    raw = ocr.raw_text or ""
    raw_len = len(raw)

    has_id_signals = any(kw in raw for kw in ID_CARD_KEYWORDS)
    has_bank_signals = any(kw in raw for kw in BANK_KEYWORDS)

    # 명확히 mismatch → 바로 invalid_doc_type
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

    # 명확히 match → 통과
    if expected_type == DocumentType.ID_CARD and has_id_signals:
        return None
    if expected_type == DocumentType.BANK_ACCOUNT_DOC and has_bank_signals:
        return None

    # 애매한 경우: 키워드 없음 / 양쪽 혼재 / OCR 텍스트 부족 → VLM 호출
    is_ambiguous = (
        (not has_id_signals and not has_bank_signals)
        or (has_id_signals and has_bank_signals)
        or raw_len < MIN_RAW_TEXT_LENGTH
    )

    if is_ambiguous:
        # 키워드 없음 + 품질 문제 → 이미지 불량으로 retake
        q_issues = _quality_issues(quality)
        if q_issues:
            reason = "; ".join(q_issues) + "; OCR could not identify document type"
            return _response(expected_type, Decision.RETAKE, reason, quality, ocr)
        return _gate2_vlm_fallback(image_path, expected_type, quality, ocr, on_progress=on_progress)

    return None


def _gate2_vlm_fallback(image_path: str, expected_type: DocumentType, quality: ImageQualityResult, ocr: OCRResult, on_progress=None) -> DocumentReviewResponse | None:
    """VLM으로 문서 유형을 분류한다."""
    from app.services.vlm_service import classify_document_type

    _notify = on_progress or (lambda msg: None)
    _notify("🤖 VLM으로 문서를 분석하고 있습니다...")

    vlm_type, vlm_desc = classify_document_type(image_path)

    expected_vlm = "id_card" if expected_type == DocumentType.ID_CARD else "bank_account"

    if vlm_type == expected_vlm:
        return None  # match → 통과

    if vlm_type == "unknown":
        reason = vlm_desc or "VLM could not determine document type"
        return _response(DocumentType.UNKNOWN, Decision.INVALID_DOC_TYPE, reason, quality, ocr)

    # VLM이 다른 타입으로 판정
    detected = DocumentType.ID_CARD if vlm_type == "id_card" else DocumentType.BANK_ACCOUNT_DOC
    reason = vlm_desc or f"Expected {'ID card' if expected_type == DocumentType.ID_CARD else 'bank account'} but VLM detected {'ID card' if vlm_type == 'id_card' else 'bank account'}"

    return _response(
        detected,
        Decision.INVALID_DOC_TYPE,
        reason,
        quality, ocr,
    )


# ──────────────────────────────────────────────
# Gate 3: 필수 정보 존재 검증
# ──────────────────────────────────────────────

def _quality_issues(quality: ImageQualityResult) -> list[str]:
    """품질 문제를 문자열 리스트로 반환한다."""
    issues = []
    if quality.blur_score is not None and quality.blur_score < BLUR_THRESHOLD:
        issues.append(f"image too blurry (score: {quality.blur_score})")
    if quality.low_resolution_detected:
        issues.append("image resolution too low")
    if quality.glare_detected:
        issues.append("glare detected on document")
    return issues


def _gate3_required_fields_id(ocr: OCRResult, quality: ImageQualityResult) -> DocumentReviewResponse | None:
    """신분증 필수 필드 존재 여부 + 품질 조합 검증."""
    raw_len = len(ocr.raw_text) if ocr.raw_text else 0
    name = _get_field(ocr, "name")
    id_number = _get_field(ocr, "id_number")
    q_issues = _quality_issues(quality)

    # OCR 결과가 극단적으로 적으면 retake
    if raw_len < MIN_RAW_TEXT_LENGTH:
        reason = "OCR extracted too little text from image"
        if q_issues:
            reason = "; ".join(q_issues) + "; " + reason
        return _response(DocumentType.ID_CARD, Decision.RETAKE, reason, quality, ocr)

    # 품질 문제 + 필수 필드 전부 없음 → retake
    if not name and not id_number:
        reason = "No required fields (name, id_number) could be extracted"
        if q_issues:
            reason = "; ".join(q_issues) + "; " + reason
        return _response(DocumentType.ID_CARD, Decision.RETAKE, reason, quality, ocr)

    # 일부 누락 또는 품질 문제
    review_reasons: list[str] = []
    if not name:
        review_reasons.append("name field not found")
    if not id_number:
        review_reasons.append("id_number field not found")

    # 품질 문제 + 일부 필드 누락 → review에 품질 언급 추가
    if q_issues and review_reasons:
        review_reasons = q_issues + review_reasons

    # 품질 문제 있지만 필드 다 있으면 → 통과 (pass 가능)

    if review_reasons:
        return _response(DocumentType.ID_CARD, Decision.REVIEW,
                         "; ".join(review_reasons), quality, ocr)

    return None


def _gate3_required_fields_bank(ocr: OCRResult, quality: ImageQualityResult) -> DocumentReviewResponse | None:
    """통장사본 필수 필드 존재 여부 + 품질 조합 검증."""
    raw_len = len(ocr.raw_text) if ocr.raw_text else 0
    name = _get_field(ocr, "name")
    account_number = _get_field(ocr, "account_number")
    bank_name = _get_field(ocr, "bank_name")
    q_issues = _quality_issues(quality)

    if raw_len < MIN_RAW_TEXT_LENGTH:
        reason = "OCR extracted too little text from image"
        if q_issues:
            reason = "; ".join(q_issues) + "; " + reason
        return _response(DocumentType.BANK_ACCOUNT_DOC, Decision.RETAKE, reason, quality, ocr)

    # 계좌번호가 가장 핵심 — 없으면 나머지와 조합하여 판단
    if not account_number:
        if not name:
            # 계좌번호 + 이름 둘 다 없음 → retake
            reason = "No required fields (account_number, name) could be extracted"
            if q_issues:
                reason = "; ".join(q_issues) + "; " + reason
            return _response(DocumentType.BANK_ACCOUNT_DOC, Decision.RETAKE, reason, quality, ocr)
        # 계좌번호 없음 + 이름만 있음 → review (핵심 정보 부재)
        review_reasons = ["account_number field not found"]
        if not bank_name:
            review_reasons.append("bank_name field not found")
        if q_issues:
            review_reasons = q_issues + review_reasons
        return _response(DocumentType.BANK_ACCOUNT_DOC, Decision.REVIEW,
                         "; ".join(review_reasons), quality, ocr)

    # 계좌번호 있음 — 나머지 필드 확인
    review_reasons: list[str] = []
    if not name:
        review_reasons.append("name field not found")
    if not bank_name:
        review_reasons.append("bank_name field not found")

    if q_issues and review_reasons:
        review_reasons = q_issues + review_reasons

    if review_reasons:
        return _response(DocumentType.BANK_ACCOUNT_DOC, Decision.REVIEW,
                         "; ".join(review_reasons), quality, ocr)

    return None


# ──────────────────────────────────────────────
# Gate 4: 형식 검증 + 최종 확신
# ──────────────────────────────────────────────

def _check_char_confidence(field: OCRField, threshold: float = CHAR_CONFIDENCE) -> list[str]:
    """글자별 confidence를 검사하여 낮은 글자 목록 반환.
    예: ["'3' at position 5 (0.42)"]"""
    low_chars = []
    for i, cc in enumerate(field.char_confidences):
        if cc.confidence < threshold:
            low_chars.append(f"'{cc.char}' at position {i + 1} ({cc.confidence:.2f})")
    return low_chars


def _field_confidence_check(
    field: OCRField | None,
    field_name: str,
    line_threshold: float,
    review_reasons: list[str],
) -> None:
    """필드의 라인 confidence + 글자별 confidence를 검사하여 review_reasons에 추가."""
    if field is None:
        return
    if field.confidence < line_threshold:
        review_reasons.append(f"{field_name} confidence too low ({field.confidence:.2f})")
        return
    # 라인 평균은 통과했지만 특정 글자가 낮은 경우
    low_chars = _check_char_confidence(field)
    if low_chars:
        chars_desc = ", ".join(low_chars)
        review_reasons.append(f"{field_name} low confidence chars: {chars_desc}")


def _gate4_validation_id(ocr: OCRResult, quality: ImageQualityResult) -> DocumentReviewResponse | None:
    """신분증 필드별 형식 검증 및 confidence 확인 (글자별 포함)."""
    name = _get_field(ocr, "name")
    id_number = _get_field(ocr, "id_number")
    address = _get_field(ocr, "address")
    issue_date = _get_field(ocr, "issue_date")
    review_reasons: list[str] = []

    # 핵심: id_number 형식 + confidence
    if id_number:
        if not ID_NUMBER_PATTERN.match(id_number.value or ""):
            review_reasons.append(f"id_number format invalid: {id_number.value}")
        else:
            _field_confidence_check(id_number, "id_number", CRITICAL_CONFIDENCE, review_reasons)

    _field_confidence_check(name, "name", NAME_CONFIDENCE, review_reasons)
    _field_confidence_check(address, "address", SECONDARY_CONFIDENCE, review_reasons)
    _field_confidence_check(issue_date, "issue_date", SECONDARY_CONFIDENCE, review_reasons)

    if review_reasons:
        return _response(DocumentType.ID_CARD, Decision.REVIEW,
                         "; ".join(review_reasons), quality, ocr)

    return None


def _gate4_validation_bank(ocr: OCRResult, quality: ImageQualityResult) -> DocumentReviewResponse | None:
    """통장사본 필드별 형식 검증 및 confidence 확인 (글자별 포함)."""
    name = _get_field(ocr, "name")
    account_number = _get_field(ocr, "account_number")
    bank_name = _get_field(ocr, "bank_name")
    review_reasons: list[str] = []

    _field_confidence_check(account_number, "account_number", CRITICAL_CONFIDENCE, review_reasons)
    _field_confidence_check(name, "name", NAME_CONFIDENCE, review_reasons)
    _field_confidence_check(bank_name, "bank_name", SECONDARY_CONFIDENCE, review_reasons)

    if review_reasons:
        return _response(DocumentType.BANK_ACCOUNT_DOC, Decision.REVIEW,
                         "; ".join(review_reasons), quality, ocr)

    return None


# ──────────────────────────────────────────────
# 메인 평가 함수
# ──────────────────────────────────────────────

def evaluate_id_card(image_path: str, on_progress=None) -> DocumentReviewResponse:
    _notify = on_progress or (lambda msg: None)

    _notify("🔍 이미지 품질을 검사하고 있습니다...")
    quality = evaluate_quality(image_path)

    # Gate 1: 입력 유효성
    result = _gate1_input_validity(image_path, quality, DocumentType.ID_CARD)
    if result:
        return result

    _notify("📝 문서에서 텍스트를 추출하고 있습니다...")
    ocr = extract_id_card(image_path)

    # Gate 2: 문서 유형
    _notify("🔎 문서 유형을 확인하고 있습니다...")
    result = _gate2_document_type(ocr, DocumentType.ID_CARD, quality, image_path, on_progress=on_progress)
    if result:
        return result

    # Gate 3: 필수 정보
    _notify("✅ 추출된 정보를 검증하고 있습니다...")
    result = _gate3_required_fields_id(ocr, quality)
    if result:
        return result

    # Gate 4: 형식 검증
    result = _gate4_validation_id(ocr, quality)
    if result:
        return result

    # Pass
    return _response(DocumentType.ID_CARD, Decision.PASS,
                     "모든 필수 정보가 정상적으로 확인되었습니다", quality, ocr)


def evaluate_bank_account(image_path: str, on_progress=None) -> DocumentReviewResponse:
    _notify = on_progress or (lambda msg: None)

    _notify("🔍 이미지 품질을 검사하고 있습니다...")
    quality = evaluate_quality(image_path)

    # Gate 1: 입력 유효성
    result = _gate1_input_validity(image_path, quality, DocumentType.BANK_ACCOUNT_DOC)
    if result:
        return result

    _notify("📝 문서에서 텍스트를 추출하고 있습니다...")
    ocr = extract_bank_account(image_path)

    # Gate 2: 문서 유형
    _notify("🔎 문서 유형을 확인하고 있습니다...")
    result = _gate2_document_type(ocr, DocumentType.BANK_ACCOUNT_DOC, quality, image_path, on_progress=on_progress)
    if result:
        return result

    # Gate 3: 필수 정보
    _notify("✅ 추출된 정보를 검증하고 있습니다...")
    result = _gate3_required_fields_bank(ocr, quality)
    if result:
        return result

    # Gate 4: 형식 검증
    result = _gate4_validation_bank(ocr, quality)
    if result:
        return result

    # Pass
    return _response(DocumentType.BANK_ACCOUNT_DOC, Decision.PASS,
                     "모든 필수 정보가 정상적으로 확인되었습니다", quality, ocr)


def _retake_reason(quality: ImageQualityResult) -> str:
    reasons = []
    if quality.blur_score is not None and quality.blur_score < 100:
        reasons.append(f"image too blurry (score: {quality.blur_score})")
    if quality.glare_detected:
        reasons.append("glare detected")
    if quality.low_resolution_detected:
        reasons.append("image resolution too low")
    return "; ".join(reasons) if reasons else "image quality unacceptable"
