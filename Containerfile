FROM python:3.12-slim

WORKDIR /app/

RUN pip install poetry

COPY poetry.lock pyproject.toml ./

RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

COPY ./asu/ ./asu/

COPY ./misc/config.py /etc/asu/config.py

CMD uvicorn --host 0.0.0.0 'asu.main:app'
