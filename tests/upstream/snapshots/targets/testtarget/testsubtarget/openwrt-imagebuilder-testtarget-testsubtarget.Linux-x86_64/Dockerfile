FROM alpine

RUN apk add make bash

RUN adduser -D buildbot -h /builder/

USER buildbot

ADD ./ /builder/

WORKDIR /builder/
