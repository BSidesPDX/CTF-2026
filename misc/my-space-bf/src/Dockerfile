FROM alpine:latest

RUN apk update && apk add bash ed grep socat

COPY . /var/chal/

RUN chmod -R o=r /var/chal \
 && chmod o+x /var/chal /var/chal/run-challenge.sh /var/chal/bf.sh \
 && adduser -D -H -s /bin/bash bff \
 && echo -e "#!/bin/bash\n/bin/ed --restricted" > /usr/local/bin/ed \
 && chmod +x /usr/local/bin/ed

WORKDIR /var/chal

USER bff

EXPOSE 22333/tcp

CMD ["./run-challenge.sh"]
