from app.schemas.decision import Decision, DocumentReviewResponse
from app.schemas.document import DocumentType
from app.schemas.ocr import OCRField, OCRResult
from app.schemas.quality import ImageQualityResult

# 1. pass 케이스: 정상 신분증
pass_response = DocumentReviewResponse(
    document_type=DocumentType.ID_CARD,
    decision=Decision.PASS,
    reason="All required fields extracted with high confidence",
    quality=ImageQualityResult(
        blur_score=12.5,
        glare_detected=False,
        crop_detected=False,
        is_acceptable=True,
    ),
    ocr=OCRResult(
        fields=[
            OCRField(field_name="name", value="홍길동", confidence=0.95),
            OCRField(field_name="id_number", value="901215-1234567", confidence=0.92),
        ],
        raw_text="홍길동 901215-1234567 서울특별시",
    ),
)

# 2. retake 케이스: 흐릿한 이미지
retake_response = DocumentReviewResponse(
    document_type=DocumentType.UNKNOWN,
    decision=Decision.RETAKE,
    reason="Image too blurry to extract text",
    quality=ImageQualityResult(
        blur_score=85.3,
        glare_detected=False,
        crop_detected=False,
        is_acceptable=False,
    ),
    ocr=OCRResult(fields=[], raw_text=None),
)

# 3. review 케이스: OCR 신뢰도 낮음
review_response = DocumentReviewResponse(
    document_type=DocumentType.BANK_ACCOUNT_DOC,
    decision=Decision.REVIEW,
    reason="Account number extracted with low confidence",
    quality=ImageQualityResult(
        blur_score=20.1,
        glare_detected=True,
        crop_detected=False,
        is_acceptable=True,
    ),
    ocr=OCRResult(
        fields=[
            OCRField(field_name="name", value="김철수", confidence=0.88),
            OCRField(field_name="account_number", value="110-234-5678??", confidence=0.45),
        ],
        raw_text="김철수 110-234-5678 국민은행",
    ),
)

if __name__ == "__main__":
    import json

    for label, resp in [("PASS", pass_response), ("RETAKE", retake_response), ("REVIEW", review_response)]:
        print(f"=== {label} ===")
        print(json.dumps(resp.model_dump(), indent=2, ensure_ascii=False))
        print()
