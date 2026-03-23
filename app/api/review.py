import json
import os
import queue
import tempfile
import threading

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

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


def _stream_evaluate(evaluate_fn, tmp_path: str):
    """Run evaluate_fn in a thread, yielding SSE progress events."""
    q: queue.Queue = queue.Queue()

    def run():
        try:
            result = evaluate_fn(tmp_path, on_progress=lambda msg: q.put({"type": "progress", "message": msg}))
            q.put({"type": "result", "data": result.model_dump(mode="json")})
        except Exception as e:
            q.put({"type": "error", "message": str(e)})
        finally:
            os.unlink(tmp_path)

    thread = threading.Thread(target=run)
    thread.start()

    def generate():
        while True:
            item = q.get()
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            if item["type"] in ("result", "error"):
                break

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/review/id-card/stream")
async def review_id_card_stream(file: UploadFile):
    tmp_path = await _save_upload(file)
    return _stream_evaluate(evaluate_id_card, tmp_path)


@router.post("/review/bank-account/stream")
async def review_bank_account_stream(file: UploadFile):
    tmp_path = await _save_upload(file)
    return _stream_evaluate(evaluate_bank_account, tmp_path)
