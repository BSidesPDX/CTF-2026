FROM ghcr.io/baresip/docker/baresip:latest

WORKDIR /app

COPY answer.wav /app/answer.wav
COPY baresip/ /etc/baresip/
COPY --chmod=755 entrypoint.sh /entrypoint.sh

EXPOSE 5060/udp
EXPOSE 5060/tcp
EXPOSE 10000-10199/udp

CMD ["entrypoint.sh"]
