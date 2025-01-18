FROM python:3.12-slim

WORKDIR /app/

RUN pip install poetry

COPY poetry.lock pyproject.toml README.md ./

RUN poetry config virtualenvs.create false

RUN poetry install --only main --no-root --no-directory

COPY ./asu/ ./asu/

RUN poetry install --only main

CMD uvicorn --host 0.0.0.0 'asu.main:app'
