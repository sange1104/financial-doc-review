#!/bin/bash
set -e

echo "=== Starting OCRGate ==="

export STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false
export STREAMLIT_SERVER_ENABLE_CORS=false
export STREAMLIT_SERVER_HEADLESS=true

# FastAPI (background)
uvicorn app.main:app --host 0.0.0.0 --port 8001 &

# Streamlit (foreground)
streamlit run app/ui.py \
  --server.port 8501 \
  --server.address 0.0.0.0 \
  --server.enableCORS false \
  --server.enableXsrfProtection false
