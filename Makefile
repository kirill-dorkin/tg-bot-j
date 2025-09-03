.PHONY: dev test up migrate check-docker wait-for-postgres

# Prefer Docker Compose v2, fallback to v1 if unavailable
COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")
PRETTY := bash ./scripts/pretty.sh

# Disable BuildKit to avoid depending on buildkitd in restricted environments
export DOCKER_BUILDKIT ?= 0
export COMPOSE_DOCKER_CLI_BUILD ?= 0

check-docker:
	@# Ensure Docker CLI is installed
	@if ! command -v docker >/dev/null 2>&1; then \
		echo "Docker is not installed. Install Docker Desktop: https://www.docker.com/products/docker-desktop"; \
		exit 1; \
	fi
	@# Start Docker Desktop on macOS if daemon is not running
	@docker info >/dev/null 2>&1 || { \
		echo "Docker daemon is not running. Attempting to start Docker Desktop..."; \
		( command -v open >/dev/null 2>&1 && open -a Docker ) || true; \
		printf "Waiting for Docker daemon"; \
		until docker info >/dev/null 2>&1; do printf "."; sleep 2; done; \
		echo "\nDocker is up."; \
	}

dev: check-docker
	$(PRETTY) "Build app image" "$(COMPOSE) build app"
	$(PRETTY) "Start Postgres and Redis" "$(COMPOSE) up -d postgres redis"
	$(PRETTY) "Wait for Postgres" "$(MAKE) wait-for-postgres"
	$(PRETTY) "Run DB migrations" "$(COMPOSE) run --rm app python -m app.infra.migrations.run upgrade"
	@echo "\n🚀 Starting bot (attached). Press Ctrl+C to stop; use '$(COMPOSE) down' to stop services.\n"
	$(COMPOSE) up app

test:
	pytest -q

up: check-docker
	$(PRETTY) "Build images" "$(COMPOSE) build"
	$(COMPOSE) up

migrate: check-docker
	$(PRETTY) "Start Postgres and Redis" "$(COMPOSE) up -d postgres redis"
	$(PRETTY) "Wait for Postgres" "$(MAKE) wait-for-postgres"
	$(PRETTY) "Run DB migrations" "$(COMPOSE) run --rm app python -m app.infra.migrations.run upgrade"

wait-for-postgres:
	@until $(COMPOSE) exec -T postgres pg_isready -U user >/dev/null 2>&1; do sleep 1; done
