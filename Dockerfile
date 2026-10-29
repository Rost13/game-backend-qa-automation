FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.lock pyproject.toml README.md ./
RUN python -m pip install --no-cache-dir --requirement requirements.lock

COPY src ./src
COPY fixtures ./fixtures
COPY tests ./tests
COPY conftest.py ./conftest.py
RUN python -m pip install --no-cache-dir --no-deps . \
    && useradd --create-home --uid 10001 qa \
    && chown -R qa:qa /app

USER qa

CMD ["pytest", "--alluredir=allure-results"]
