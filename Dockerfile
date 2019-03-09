FROM debian:9

RUN apt update && apt install -y \
python3-pip \
odbc-postgresql \
unixodbc-dev \
gunicorn3 \
git \
bash \
netcat \
wget \
&& rm -rf /var/lib/apt/lists/*

RUN apt update && apt install -y \
subversion g++ zlib1g-dev build-essential git python rsync man-db \
libncurses5-dev gawk gettext unzip file libssl-dev wget zip time \
&& rm -rf /var/lib/apt/lists/*

COPY . /asu
COPY odbc.ini ~/.odbc.ini
WORKDIR /asu

RUN pip3 install -e .

EXPOSE 8000
