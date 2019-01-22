FROM debian:9

RUN apt update && apt install -y \
python3-pip \
odbc-postgresql \
unixodbc-dev \
gunicorn3 \
git \
bash \
netcat \
&& rm -rf /var/lib/apt/lists/*

COPY . /asu
WORKDIR /asu

RUN pip3 install -e .
 
EXPOSE 5000
