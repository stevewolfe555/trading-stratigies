# Minimal PHP CLI image with pcntl + sockets and Composer for Reverb / relay
FROM php:8.3-cli-alpine

# Install build deps and PHP extensions required by Reverb and Laravel CLI
RUN apk add --no-cache git bash libzip-dev libpq-dev $PHPIZE_DEPS \
 && docker-php-ext-install pcntl sockets \
 && apk del $PHPIZE_DEPS || true

# Install Composer
COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

WORKDIR /app

# Default command is overridden by docker-compose service commands
CMD ["php", "-v"]
