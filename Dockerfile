FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Keep dependency install simple for this minimal project.
RUN pip install --no-cache-dir \
    "fastapi[standard]>=0.135.1,<0.136.0" \
    "sqlalchemy>=2.0.36,<3.0.0" \
    "psycopg[binary]>=3.2.3,<4.0.0"

COPY src /app/src
COPY data /app/data

EXPOSE 8000

CMD ["sh", "-c", "uvicorn team_bbs.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
