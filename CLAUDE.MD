# Project Context

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