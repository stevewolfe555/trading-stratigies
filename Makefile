SHELL := /bin/bash

.DEFAULT_GOAL := help

help:
	@echo "Targets:"
	@echo "  up           Start all services"
	@echo "  down         Stop all services"
	@echo "  build        Build images"
	@echo "  logs         Tail logs"
	@echo "  restart      Restart services"
	@echo "  psql         Open psql in db container"
	@echo "  redis-cli    Open redis-cli in redis container"
	@echo "  bootstrap    Create .env from example"

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

restart:
	docker compose down
	docker compose up -d

psql:
	docker compose exec -e PAGER=cat db psql -U postgres -d trading

redis-cli:
	docker compose exec redis redis-cli

bootstrap:
	@if [ ! -f .env ]; then cp .env.example .env; echo ".env created"; else echo ".env already exists"; fi
