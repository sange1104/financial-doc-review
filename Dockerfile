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

# Upgrade pip first (Ubuntu 22.04 ships pip 22.x which can't parse PaddlePaddle index)
RUN pip install --upgrade pip

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir \
    torch==2.4.1+cu118 torchvision==0.19.1+cu118 --index-url https://download.pytorch.org/whl/cu118 \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir transformers==5.3.0 qwen-vl-utils accelerate

# Install paddlepaddle-gpu 3.0.0 from local wheel (not available on PyPI)
COPY paddle_gpu_3.0.0.tar.gz /tmp/paddle_gpu_3.0.0.tar.gz
RUN mkdir -p /tmp/paddle_gpu && tar xzf /tmp/paddle_gpu_3.0.0.tar.gz -C /usr/local/lib/python3.10/dist-packages/ \
    && pip install --no-cache-dir opt_einsum httpx astor networkx decorator \
    && rm -rf /tmp/paddle_gpu_3.0.0.tar.gz /tmp/paddle_gpu

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
