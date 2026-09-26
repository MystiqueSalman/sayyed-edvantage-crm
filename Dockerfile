# Sayyed EdVantage CRM + AI Agent
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# The CRM dashboard itself is stdlib-only; these are for the AI Agent API.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Hosting platforms (Railway / Render / Heroku) inject $PORT automatically.
EXPOSE 8000

# Default: run the CRM dashboard. The AI Agent API is started separately
# (see docker-compose.yml) or via: uvicorn app.main:app --host 0.0.0.0 --port 8001
CMD ["python", "Sayyed_EdVantage_CRM_BATCH1.py"]
