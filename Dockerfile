FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps + Python 3.10
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 python3.10-dev python3.10-venv python3-pip \
    libgl1-mesa-glx libglib2.0-0 gcc g++ \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir \
    torch==2.4.1+cu118 torchvision==0.19.1+cu118 --index-url https://download.pytorch.org/whl/cu118 \
    && pip install --no-cache-dir \
    paddlepaddle-gpu==3.0.0 -f https://www.paddlepaddle.org.cn/whl/linux/cudnn/stable.html \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir transformers==5.3.0 qwen-vl-utils accelerate

# App code
COPY app/ app/
COPY scripts/ scripts/
COPY samples/ samples/
COPY pyproject.toml .

# Environment
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
ENV VLM_BASE=/nonexistent

# Ports: FastAPI 8001, Streamlit 8501
EXPOSE 8001 8501

COPY start.sh .
RUN chmod +x start.sh

CMD ["./start.sh"]
