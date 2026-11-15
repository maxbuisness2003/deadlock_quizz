FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DQ_DATA_DIR=/app/data \
    PORT=8001

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY data/quiz.db ./data/quiz.db
COPY run.py ./

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx,sys; sys.exit(0 if httpx.get('http://127.0.0.1:'+__import__('os').environ.get('PORT','8001')+'/healthz', timeout=4).status_code == 200 else 1)"

# PORT подставляется хостингом (Render, Hugging Face Spaces, Railway)
CMD ["sh", "-c", "python run.py --host 0.0.0.0 --port ${PORT:-8001}"]
