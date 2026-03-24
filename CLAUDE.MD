# Project Context

## Environment

- Use conda environment `ocr` as the default environment.
  - Activate with: `conda activate ocr`
- GPU 0번을 지정하여 실행해야 한다.
  - API 서버: `CUDA_VISIBLE_DEVICES=0 conda run -n ocr uvicorn app.main:app --host 0.0.0.0 --port 8001`
  - UI 서버: `conda run -n ocr streamlit run app/ui.py --server.port 8501 --server.address 0.0.0.0`
  - 평가 스크립트: `CUDA_VISIBLE_DEVICES=0 conda run -n ocr python scripts/eval_samples.py`
  - `--reload` 옵션은 PaddleOCR C++ 백엔드 충돌을 유발하므로 사용하지 않는다. 코드 수정 시 서버를 수동 재시작한다.

## Goal
Build an MVP for financial document review as a decision-making problem under imperfect inputs.

## Scope
- Document types: id_card, bank_account_doc
- Decisions: pass, retake, review
- No fine-tuning in MVP
- OCR + rule-based pipeline first
- Optional VLM as secondary reviewer

## Coding Rules
- Use Python 3.10+
- Prefer small, modular functions
- Keep business rules in a separate rule_engine module
- All API outputs must follow Pydantic schemas
- Avoid hardcoding sample-specific logic

## Current Priorities
1. Define schema
2. Implement OCR pipeline
3. Add quality checks
4. Build FastAPI endpoint
5. Connect Streamlit UI