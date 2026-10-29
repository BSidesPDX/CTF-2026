FROM php:8.5.12-apache

# Install GD extension for image processing
RUN apt-get update && apt-get install -y \
    libfreetype6-dev \
    libjpeg62-turbo-dev \
    libpng-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j$(nproc) gd

# Enable Apache modules
RUN a2enmod rewrite status proxy proxy_http remoteip

# Set working directory
WORKDIR /var/www/html

# Copy in web files
COPY company     /var/www/html
COPY apache.conf /etc/apache2/sites-available/tangerineprinting.biz.conf
COPY php.ini     /usr/local/etc/php/php.ini

RUN a2ensite tangerineprinting.biz
