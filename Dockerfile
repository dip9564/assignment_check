FROM python:3.11-slim

WORKDIR /app

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