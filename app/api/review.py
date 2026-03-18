import os
import tempfile

from fastapi import APIRouter, HTTPException, UploadFile

from app.schemas.decision import DocumentReviewResponse
from app.services.ocr_service import extract_ocr
from app.services.quality_service import evaluate_quality
from app.services.rule_engine import decide

router = APIRouter()


@router.post("/review", response_model=DocumentReviewResponse)
async def review_document(file: UploadFile):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are supported")

    suffix = os.path.splitext(file.filename or ".png")[1]

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        quality = evaluate_quality(tmp_path)
        ocr = extract_ocr(tmp_path)
        result = decide(quality, ocr)
    finally:
        os.unlink(tmp_path)

    return result
