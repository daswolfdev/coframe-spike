FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn
COPY app.py config.seed.json ./
ENV API_WORKERS=1
# shell form so API_WORKERS expands; multi-process writers are measured-safe
CMD uvicorn app:app --host 0.0.0.0 --port 8080 --workers "$API_WORKERS"
