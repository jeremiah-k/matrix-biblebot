# ============================================================
# Matrix BibleBot - Docker Management
# ============================================================

DOCKER_COMPOSE := $(shell docker compose version > /dev/null 2>&1 && echo "docker compose" || echo "docker-compose")
IMAGE_NAME     := ghcr.io/jeremiah-k/matrix-biblebot
CONTAINER_NAME := matrix-biblebot
CONFIG_DIR     := $(HOME)/.config/matrix-biblebot

# ============================================================
# Help
# ============================================================

.PHONY: help
help:
	@echo ""
	@echo "Matrix BibleBot - Docker Commands"
	@echo "=================================="
	@echo ""
	@echo "  make build         Build Docker image (with layer caching)"
	@echo "  make build-nocache Build Docker image without cache"
	@echo "  make rebuild       Stop, rebuild (no cache), and restart"
	@echo "  make run           Start container in detached mode"
	@echo "  make stop          Stop container"
	@echo "  make logs          Follow container logs"
	@echo "  make shell         Open a shell inside the running container"
	@echo "  make clean         Remove containers and networks"
	@echo "  make config        Set up config directory and files"
	@echo "  make edit          Edit config file with preferred editor"
	@echo ""

# ============================================================
# Build
# ============================================================

.PHONY: build build-nocache rebuild

build:
	@echo "Building $(IMAGE_NAME)..."
	$(DOCKER_COMPOSE) build

build-nocache:
	@echo "Building $(IMAGE_NAME) without cache..."
	$(DOCKER_COMPOSE) build --no-cache

rebuild: stop build-nocache run

# ============================================================
# Runtime
# ============================================================

.PHONY: run stop logs shell

run:
	@echo "Starting $(CONTAINER_NAME)..."
	UID=$(shell id -u) GID=$(shell id -g) $(DOCKER_COMPOSE) up -d

stop:
	@echo "Stopping $(CONTAINER_NAME)..."
	$(DOCKER_COMPOSE) stop

logs:
	$(DOCKER_COMPOSE) logs -f

shell:
	@echo "Opening shell in $(CONTAINER_NAME)..."
	docker exec -it $(CONTAINER_NAME) /bin/bash || docker exec -it $(CONTAINER_NAME) /bin/sh

# ============================================================
# Cleanup
# ============================================================

.PHONY: clean

clean:
	@echo "Removing containers and networks..."
	$(DOCKER_COMPOSE) down --remove-orphans

# ============================================================
# Configuration
# ============================================================

.PHONY: config edit

config:
	@mkdir -p $(CONFIG_DIR)
	@if [ ! -f $(CONFIG_DIR)/config.yaml ]; then \
		echo "Copying sample config to $(CONFIG_DIR)/config.yaml..."; \
		cp sample_config.yaml $(CONFIG_DIR)/config.yaml; \
	else \
		echo "Config already exists at $(CONFIG_DIR)/config.yaml"; \
	fi
	@if [ ! -f docker-compose.yaml ]; then \
		echo "Creating docker-compose.yaml from sample..."; \
		cp sample-docker-compose.yaml docker-compose.yaml; \
	else \
		echo "docker-compose.yaml already exists"; \
	fi

edit:
	@if [ ! -f $(CONFIG_DIR)/config.yaml ]; then \
		echo "Config not found. Run 'make config' first."; \
		exit 1; \
	fi
	@echo "Select editor:"
	@echo "  1) nano"
	@echo "  2) vim"
	@echo "  3) emacs"
	@echo "  4) code (VS Code)"
	@echo "  5) gedit"
	@echo "  6) other"
	@read -p "Enter choice [1-6]: " choice; \
	case $$choice in \
		1) EDITOR_CMD="nano" ;; \
		2) EDITOR_CMD="vim" ;; \
		3) EDITOR_CMD="emacs" ;; \
		4) EDITOR_CMD="code" ;; \
		5) EDITOR_CMD="gedit" ;; \
		6) read -p "Enter editor command: " EDITOR_CMD ;; \
		*) EDITOR_CMD="nano" ;; \
	esac; \
	echo "Opening config with $$EDITOR_CMD..."; \
	$$EDITOR_CMD $(CONFIG_DIR)/config.yaml
