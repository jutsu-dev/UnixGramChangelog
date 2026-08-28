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
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "from unixgram_changelog.config import Settings; Settings(); print('ok')" || exit 1
CMD ["unixgram-changelog"]
