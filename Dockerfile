FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Keep dependency install simple for this minimal project.
RUN pip install --no-cache-dir "fastapi[standard]>=0.135.1,<0.136.0"

COPY src /app/src
COPY data /app/data

EXPOSE 8000

CMD ["uvicorn", "team_bbs.main:app", "--host", "0.0.0.0", "--port", "8000"]
