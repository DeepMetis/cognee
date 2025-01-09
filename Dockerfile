FROM python:3.12-bookworm

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update && apt-get install -y gcc libpq-dev && pip install uv

COPY LICENSE LICENSE

COPY README.md README.md

COPY pyproject.toml pyproject.toml

COPY uv.lock uv.lock

ADD cognee cognee

RUN uv sync --frozen --no-dev --python-preference system -v

COPY alembic.ini alembic.ini

COPY alembic/ alembic/

ENV PATH="/app/.venv/bin:$PATH"

CMD ["uv", "run", "uvicorn", "cognee.api.client:app", "--host", "0.0.0.0", "--port","8000"]
