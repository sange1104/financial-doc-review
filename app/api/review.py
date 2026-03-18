import os
import tempfile

from fastapi import APIRouter, HTTPException, UploadFile

from app.schemas.decision import DocumentReviewResponse
from app.services.rule_engine import evaluate

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
        result = evaluate(tmp_path)
    finally:
        os.unlink(tmp_path)

    return result
