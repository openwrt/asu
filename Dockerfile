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

RUN useradd -c "OpenWrt Build Server" -m -d /home/asu -s /bin/bash asu
COPY --chown=asu:asu . /opt/asu/
COPY --chown=asu:asu asu/utils/config.yml.default /etc/asu/config.yml
COPY --chown=asu:asu asu/utils/distributions /etc/asu/
RUN mkdir -p /var/lib/asu/ /var/cache/asu/
RUN chown asu:asu /opt/asu/ /var/lib/asu/ /var/cache/asu/
USER asu
ENV HOME /home/asu/
WORKDIR /opt/asu/
ENV PATH="/home/asu/.local/bin:${PATH}"
RUN pip3 install -e .
COPY ./contrib/odbc.ini_docker /home/asu/.odbc.ini

EXPOSE 8000
