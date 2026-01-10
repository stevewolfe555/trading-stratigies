# Minimal PHP CLI image with pcntl + sockets and Composer for Reverb / relay
FROM php:8.3-cli

# Install build deps and PHP extensions required by Reverb and Laravel CLI
RUN apt-get update \
 && apt-get install -y --no-install-recommends git libzip-dev libpq-dev \
 && docker-php-ext-install pcntl sockets pdo_pgsql pgsql \
 && rm -rf /var/lib/apt/lists/*

# Install Composer
COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

WORKDIR /app

# Default command is overridden by docker-compose service commands
CMD ["php", "-v"]
