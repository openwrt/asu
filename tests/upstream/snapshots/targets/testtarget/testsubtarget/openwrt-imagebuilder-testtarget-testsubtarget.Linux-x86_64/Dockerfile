FROM alpine

RUN apk add make bash

RUN adduser -D builder -h /builder/

USER builder 

ADD ./ /builder/

WORKDIR /builder/

