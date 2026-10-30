FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/tmp/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/tmp/sentence-transformers

WORKDIR /service

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY app ./app
COPY phase14 ./phase14
COPY alembic ./alembic
COPY alembic.ini .

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin career \
    && chown -R 10001:10001 /service

USER 10001:10001

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
