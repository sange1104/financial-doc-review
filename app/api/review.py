import json
import logging
import os
import queue
import tempfile
import threading

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from app.schemas.decision import DocumentReviewResponse
from app.services.rule_engine import evaluate_bank_account, evaluate_id_card

router = APIRouter()
logger = logging.getLogger(__name__)


async def _save_upload(file: UploadFile) -> str:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are supported")
    suffix = os.path.splitext(file.filename or ".png")[1]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        return tmp.name


async def _safe_evaluate(evaluate_fn, tmp_path: str):
    """평가 실행 + 에러 시 적절한 HTTP 상태코드 반환."""
    try:
        return evaluate_fn(tmp_path)
    except RuntimeError as e:
        # OCR/VLM 재시도 실패 (max retries exceeded)
        logger.error("Evaluation failed after retries: %s", e)
        return JSONResponse(
            status_code=503,
            content={"detail": f"Service temporarily unavailable: {e}"},
        )
    except Exception as e:
        logger.error("Unexpected evaluation error: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal processing error: {type(e).__name__}"},
        )
    finally:
        os.unlink(tmp_path)


@router.post("/review/id-card", response_model=DocumentReviewResponse)
async def review_id_card(file: UploadFile):
    tmp_path = await _save_upload(file)
    return await _safe_evaluate(evaluate_id_card, tmp_path)


@router.post("/review/bank-account", response_model=DocumentReviewResponse)
async def review_bank_account(file: UploadFile):
    tmp_path = await _save_upload(file)
    return await _safe_evaluate(evaluate_bank_account, tmp_path)


def _stream_evaluate_async(evaluate_fn, tmp_path: str):
    """2단계 SSE: 1차 OCR 결과 즉시 전송 → VLM 보완 결과 후속 전송."""
    q: queue.Queue = queue.Queue()

    def run():
        try:
            # Phase 1: OCR only (빠름)
            fast_result = evaluate_fn(
                tmp_path,
                on_progress=lambda msg: q.put({"type": "progress", "message": msg}),
                skip_vlm=True,
            )
            q.put({"type": "result", "data": fast_result.model_dump(mode="json")})

            # Phase 2: VLM 보완이 필요한 경우만 실행
            needs_vlm = fast_result.decision.value in ("review", "retake", "invalid_doc_type")
            if needs_vlm:
                q.put({"type": "progress", "message": "🔎 VLM으로 추가 분석 중..."})
                full_result = evaluate_fn(
                    tmp_path,
                    on_progress=lambda msg: q.put({"type": "progress", "message": msg}),
                    skip_vlm=False,
                )
                # VLM 결과가 다르면 업데이트 전송
                if full_result.model_dump(mode="json") != fast_result.model_dump(mode="json"):
                    q.put({"type": "vlm_update", "data": full_result.model_dump(mode="json")})

            q.put({"type": "done"})
        except RuntimeError as e:
            logger.error("Stream evaluation failed after retries: %s", e)
            q.put({"type": "error", "message": str(e), "retryable": True})
        except Exception as e:
            logger.error("Stream unexpected error: %s", e, exc_info=True)
            q.put({"type": "error", "message": f"Internal error: {type(e).__name__}", "retryable": False})
        finally:
            os.unlink(tmp_path)

    thread = threading.Thread(target=run)
    thread.start()

    def generate():
        while True:
            item = q.get()
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            if item["type"] in ("done", "error"):
                break

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/review/id-card/stream")
async def review_id_card_stream(file: UploadFile):
    tmp_path = await _save_upload(file)
    return _stream_evaluate_async(evaluate_id_card, tmp_path)


@router.post("/review/bank-account/stream")
async def review_bank_account_stream(file: UploadFile):
    tmp_path = await _save_upload(file)
    return _stream_evaluate_async(evaluate_bank_account, tmp_path)
