FROM python:3.12-slim

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --create-home app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY drone_billing/ ./drone_billing/

RUN mkdir -p /app/output && chown -R app:app /app

USER app

ENV PYTHONUNBUFFERED=1
ENV OUTPUT_DIR=/tmp

CMD ["python", "-m", "drone_billing"]
