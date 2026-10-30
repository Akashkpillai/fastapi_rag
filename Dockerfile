FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models

WORKDIR /code

# CPU-only PyTorch: the default Linux build bundles ~3 GB of GPU libraries we don't use
RUN pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu

# Install dependencies before copying the code, so code changes don't reinstall everything
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
