FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10001 changelog
WORKDIR /app

COPY pyproject.toml README.md ./
COPY deploy ./deploy
COPY src ./src
RUN pip install --no-cache-dir .

USER changelog
VOLUME ["/app/data"]
CMD ["unixgram-changelog"]
