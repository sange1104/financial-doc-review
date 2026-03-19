import os
import tempfile

from fastapi import APIRouter, HTTPException, UploadFile

from app.schemas.decision import DocumentReviewResponse
from app.services.rule_engine import evaluate_bank_account, evaluate_id_card

router = APIRouter()


async def _save_upload(file: UploadFile) -> str:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are supported")
    suffix = os.path.splitext(file.filename or ".png")[1]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        return tmp.name


@router.post("/review/id-card", response_model=DocumentReviewResponse)
async def review_id_card(file: UploadFile):
    tmp_path = await _save_upload(file)
    try:
        return evaluate_id_card(tmp_path)
    finally:
        os.unlink(tmp_path)


@router.post("/review/bank-account", response_model=DocumentReviewResponse)
async def review_bank_account(file: UploadFile):
    tmp_path = await _save_upload(file)
    try:
        return evaluate_bank_account(tmp_path)
    finally:
        os.unlink(tmp_path)
