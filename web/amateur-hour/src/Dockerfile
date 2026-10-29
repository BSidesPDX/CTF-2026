# Use the official PHP image
FROM php:8.4-cli

RUN apt update && apt upgrade -y \
 && apt install -y git \
 && git config --global init.defaultBranch "main" \
 && git config --global user.name "A. H4ck3r" \
 && git config --global user.email "haxor@bulletproofemail.invalid"

RUN groupadd --system --gid 999 phpserver \
 && useradd --system --gid 999 --uid 999 --no-create-home phpserver

# Set the working directory
WORKDIR /var/www

# Copy files into the container
COPY . /var/www/

RUN cd /var/www/public_html \
 && git init . \
 && curl -s 'https://raw.githubusercontent.com/danielmiessler/SecLists/60e43f4d2b0251330ff18ea4fa76aabec0515dcb/Passwords/Leaked-Databases/rockyou.txt.tar.gz' | tar -xzv > banned.tmp \
 && head -n 7000 banned.tmp > .banned.1.txt \
 && tail -n +7000 banned.tmp > banned2.tmp \
 && head -n 3500 banned2.tmp > .banned.2.txt \
 && echo 'i<3php' >> .banned.2.txt \
 && tail -n 3500 banned2.tmp >> .banned.2.txt \
 && git add . && git commit -m "PLEASE can we use version control????" \
 && cd /var/www

RUN mv /var/www/false_flag /var/www/public_html/flag \
 && cp /var/www/public_html/flag /var/www/public_html/flag.txt \
 && chmod +x /var/www/ingest \
 && sed -i 's/^passthru.*$/passthru($cmd . " " . $user . " " . $pass . " " . $host . " " . $uname); echo("success");/' /var/www/public_html/callback.php
# ^ is an intentional difference from committed, for flavor

EXPOSE 8000

USER phpserver

# Command to run the PHP server on port 8000
CMD ["php", "-S", "0.0.0.0:8000", "-t", "public_html"]
