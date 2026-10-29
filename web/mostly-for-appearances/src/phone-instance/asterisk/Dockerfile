FROM andrius/asterisk:latest

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-server ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /var/run/sshd

ARG ROOT_PASSWORD=root

RUN echo "root:${ROOT_PASSWORD}" | chpasswd

RUN printf '%s\n' \
    'PasswordAuthentication yes' \
    'PermitRootLogin yes' \
    >> /etc/ssh/sshd_config

COPY start-asterisk-sshd.sh /usr/local/bin/start-asterisk-sshd.sh
RUN chmod 0755 /usr/local/bin/start-asterisk-sshd.sh

COPY config/extensions.conf /etc/asterisk/extensions.conf
COPY config/pjsip.conf /etc/asterisk/pjsip.conf

CMD /usr/local/bin/start-asterisk-sshd.sh & /usr/sbin/asterisk -f
