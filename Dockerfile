FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e . && pip cache purge

COPY app/ ./app/

RUN useradd -r -u 1001 -s /sbin/nologin verity
USER verity

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
