FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium

COPY instagram_analyzer ./instagram_analyzer
COPY backend ./backend
COPY main.py ./main.py

EXPOSE 8000

CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
