FROM python:3

WORKDIR /usr/src/app

COPY ./misc/config.py config.py

RUN pip install --no-cache-dir gunicorn asu

CMD [ "gunicorn", "asu.asu:create_app()" ]

EXPOSE 8000
