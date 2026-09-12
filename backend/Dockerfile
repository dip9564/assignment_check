FROM python:3.11-slim

WORKDIR /app

# Install Tesseract OCR
RUN apt-get update && \
    apt-get install -y --no-install-recommends tesseract-ocr && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install \
    --no-cache-dir \
    --default-timeout=1000 \
    --retries 10 \
    torch==2.5.1 \
    --index-url https://download.pytorch.org/whl/cpu

RUN pip install \
    --no-cache-dir \
    --default-timeout=1000 \
    --retries 10 \
    -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]