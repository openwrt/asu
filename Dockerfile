FROM debian:latest

RUN apt-get update -qq &&\
    apt-get install -y \
        bash \
        build-essential \
        curl \
        file \
        gawk \
        gettext \
        git \
        gunicorn3 \
        libncurses5-dev \
        libssl-dev \
        netcat \
        odbc-postgresql \
        postgresql-client \
        python2.7 \
        python3 \
        python3-pip \
        rsync \
        signify-openbsd \
        subversion \
        swig \
        unixodbc-dev \
        unzip \
        wget \
        zlib1g-dev \
        && apt-get -y autoremove && apt-get clean

COPY . /asu/
COPY ./contrib/odbc.ini_docker /root/.odbc.ini
WORKDIR /asu/

RUN pip3 install -e .

EXPOSE 8000
