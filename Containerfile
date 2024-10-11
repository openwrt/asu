FROM python:3.12-slim

WORKDIR /app/

RUN pip install poetry

COPY poetry.lock pyproject.toml ./

RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

COPY ./asu/ ./asu/
RUN --mount=type=bind,source=./.env,target=/tmp/.env \
    grep -vE 'REDIS_URL|PUBLIC_PATH' /tmp/.env > ./.env

CMD uvicorn --host 0.0.0.0 'asu.main:app'
