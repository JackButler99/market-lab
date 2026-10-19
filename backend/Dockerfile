FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 MARKET_ENV=production HOST=0.0.0.0 PORT=10000 DATABASE_PATH=/var/data/research.sqlite3
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-production.txt ./
RUN python -m pip install --no-cache-dir -r requirements-production.txt
COPY *.py ./
EXPOSE 10000
CMD ["python", "serve.py"]
