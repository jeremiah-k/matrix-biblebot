# Matrix BibleBot - Docker Management

DOCKER_COMPOSE := $(shell docker compose version > /dev/null 2>&1 && echo "docker compose" || echo "docker-compose")
IMAGE_NAME := ghcr.io/jeremiah-k/matrix-biblebot
LOCAL_IMAGE_NAME := matrix-biblebot:local
CONTAINER_NAME := matrix-biblebot

BIBLEBOT_HOST_HOME ?= $(HOME)/.config/matrix-biblebot
RUNTIME_CONFIG_FILE := $(BIBLEBOT_HOST_HOME)/config.yaml
SAMPLE_CONFIG_FILE := src/biblebot/tools/sample_config.yaml

COMPOSE_FILE := docker-compose.yaml
COMPOSE_SOURCE_FILE := docker-compose.source.yaml
SAMPLE_COMPOSE_FILE := sample-docker-compose.yaml
SAMPLE_COMPOSE_SOURCE_FILE := sample-docker-compose.source.yaml

COMPOSE_ARGS = -f $(COMPOSE_FILE) $(if $(wildcard $(COMPOSE_SOURCE_FILE)),-f $(COMPOSE_SOURCE_FILE))
DOCKER_COMPOSE_RUN = env BIBLEBOT_HOST_HOME="$(BIBLEBOT_HOST_HOME)" UID="$(shell id -u)" GID="$(shell id -g)" $(DOCKER_COMPOSE) $(COMPOSE_ARGS)

.PHONY: help build build-nocache rebuild pull run stop logs shell clean config config-check auth-login auth-status edit setup setup-prebuilt use-prebuilt use-source update-compose

help:
	@echo ""
	@echo "Matrix BibleBot Docker Commands"
	@echo "==============================="
	@echo ""
	@echo "  make setup          Initialize runtime dir + prebuilt compose setup"
	@echo "  make setup-prebuilt Same as setup (explicit prebuilt mode)"
	@echo "  make pull           Pull prebuilt Docker image"
	@echo "  make build          Build Docker image from source mode"
	@echo "  make build-nocache  Build Docker image from source mode without cache"
	@echo "  make rebuild        Stop, rebuild source image (no cache), and restart"
	@echo "  make run            Start container in detached mode"
	@echo "  make stop           Stop container"
	@echo "  make logs           Follow container logs"
	@echo "  make shell          Open a shell inside the running container"
	@echo "  make clean          Remove containers and networks"
	@echo "  make config         Scaffold runtime directory and sample config"
	@echo "  make config-check   Validate runtime config inside the container"
	@echo "  make auth-login     Login to Matrix and save credentials under runtime dir"
	@echo "  make auth-status    Show saved auth status inside the container"
	@echo "  make edit           Edit runtime config file"
	@echo "  make use-prebuilt   Use prebuilt GHCR image"
	@echo "  make use-source     Enable local source builds via compose override"
	@echo "  make update-compose Refresh local compose files from sample templates"
	@echo ""
	@echo "Runtime directory on host: $(BIBLEBOT_HOST_HOME)"
	@echo "Container runtime directory: /data (BIBLEBOT_HOME=/data)"

config:
	@mkdir -p "$(BIBLEBOT_HOST_HOME)"
	@if [ ! -f "$(RUNTIME_CONFIG_FILE)" ]; then \
		echo "Copying sample config to $(RUNTIME_CONFIG_FILE)"; \
		cp "$(SAMPLE_CONFIG_FILE)" "$(RUNTIME_CONFIG_FILE)"; \
	else \
		echo "Config already exists at $(RUNTIME_CONFIG_FILE)"; \
	fi
	@if [ ! -f "$(COMPOSE_FILE)" ]; then \
		echo "Creating $(COMPOSE_FILE) from $(SAMPLE_COMPOSE_FILE)"; \
		cp "$(SAMPLE_COMPOSE_FILE)" "$(COMPOSE_FILE)"; \
	else \
		echo "$(COMPOSE_FILE) already exists"; \
	fi

edit:
	@if [ ! -f "$(RUNTIME_CONFIG_FILE)" ]; then \
		echo "Config not found. Run 'make config' first."; \
		exit 1; \
	fi
	@if [ -n "$$EDITOR" ]; then \
		echo "Opening with $$EDITOR"; \
		"$$EDITOR" "$(RUNTIME_CONFIG_FILE)"; \
		exit $$?; \
	fi
	@if command -v nano >/dev/null 2>&1; then \
		echo "EDITOR not set. Opening with nano."; \
		nano "$(RUNTIME_CONFIG_FILE)"; \
		exit $$?; \
	fi
	@if command -v vim >/dev/null 2>&1; then \
		echo "EDITOR not set. Opening with vim."; \
		vim "$(RUNTIME_CONFIG_FILE)"; \
		exit $$?; \
	fi
	@printf "No default editor found. Enter editor command: "; \
	read -r EDITOR_CMD; \
	"$$EDITOR_CMD" "$(RUNTIME_CONFIG_FILE)"

setup: setup-prebuilt

setup-prebuilt: config use-prebuilt
	@echo "Prebuilt mode ready. Runtime host path: $(BIBLEBOT_HOST_HOME)"
	@echo "Set room IDs in $(RUNTIME_CONFIG_FILE), then run:"
	@echo "  make auth-login"
	@echo "  make run"

use-prebuilt:
	@if [ ! -f "$(COMPOSE_FILE)" ]; then \
		cp "$(SAMPLE_COMPOSE_FILE)" "$(COMPOSE_FILE)"; \
	fi
	@if [ -f "$(COMPOSE_SOURCE_FILE)" ]; then \
		rm -f "$(COMPOSE_SOURCE_FILE)"; \
		echo "Switched to prebuilt image mode."; \
	else \
		echo "Already using prebuilt image mode."; \
	fi

use-source:
	@if [ ! -f "$(COMPOSE_FILE)" ]; then \
		cp "$(SAMPLE_COMPOSE_FILE)" "$(COMPOSE_FILE)"; \
	fi
	@cp "$(SAMPLE_COMPOSE_SOURCE_FILE)" "$(COMPOSE_SOURCE_FILE)"
	@echo "Switched to source build mode (compose override enabled)."

update-compose:
	@cp "$(SAMPLE_COMPOSE_FILE)" "$(COMPOSE_FILE)"
	@if [ -f "$(COMPOSE_SOURCE_FILE)" ]; then \
		cp "$(SAMPLE_COMPOSE_SOURCE_FILE)" "$(COMPOSE_SOURCE_FILE)"; \
	fi
	@echo "Compose files refreshed from sample templates."

pull:
	@if [ ! -f "$(COMPOSE_FILE)" ]; then \
		echo "Missing $(COMPOSE_FILE). Run 'make setup' first."; \
		exit 1; \
	fi
	@echo "Pulling prebuilt image..."
	@$(DOCKER_COMPOSE_RUN) pull

build:
	@if [ ! -f "$(COMPOSE_SOURCE_FILE)" ]; then \
		echo "Source build mode is not enabled."; \
		echo "Run 'make use-source' before 'make build', or run 'make pull' for prebuilt mode."; \
		exit 1; \
	fi
	@echo "Building $(IMAGE_NAME) with compose source override..."
	@$(DOCKER_COMPOSE_RUN) build

build-nocache:
	@if [ ! -f "$(COMPOSE_SOURCE_FILE)" ]; then \
		echo "Source build mode is not enabled."; \
		echo "Run 'make use-source' before 'make build-nocache', or run 'make pull' for prebuilt mode."; \
		exit 1; \
	fi
	@echo "Building $(IMAGE_NAME) without cache using compose source override..."
	@$(DOCKER_COMPOSE_RUN) build --no-cache

rebuild: stop build-nocache run

run:
	@if [ ! -f "$(COMPOSE_FILE)" ]; then \
		echo "Missing $(COMPOSE_FILE). Run 'make setup' first."; \
		exit 1; \
	fi
	@echo "Starting $(CONTAINER_NAME)..."
	@$(DOCKER_COMPOSE_RUN) up -d

stop:
	@if [ ! -f "$(COMPOSE_FILE)" ]; then \
		echo "Missing $(COMPOSE_FILE). Nothing to stop."; \
		exit 0; \
	fi
	@echo "Stopping $(CONTAINER_NAME)..."
	@$(DOCKER_COMPOSE_RUN) stop

logs:
	@if [ ! -f "$(COMPOSE_FILE)" ]; then \
		echo "Missing $(COMPOSE_FILE). Run 'make setup' first."; \
		exit 1; \
	fi
	@$(DOCKER_COMPOSE_RUN) logs -f

config-check:
	@if [ ! -f "$(COMPOSE_FILE)" ]; then \
		echo "Missing $(COMPOSE_FILE). Run 'make setup' first."; \
		exit 1; \
	fi
	@$(DOCKER_COMPOSE_RUN) run --rm biblebot biblebot config check

auth-login:
	@if [ ! -f "$(COMPOSE_FILE)" ]; then \
		echo "Missing $(COMPOSE_FILE). Run 'make setup' first."; \
		exit 1; \
	fi
	@$(DOCKER_COMPOSE_RUN) run --rm biblebot biblebot auth login

auth-status:
	@if [ ! -f "$(COMPOSE_FILE)" ]; then \
		echo "Missing $(COMPOSE_FILE). Run 'make setup' first."; \
		exit 1; \
	fi
	@$(DOCKER_COMPOSE_RUN) run --rm biblebot biblebot auth status

shell:
	@if [ ! -f "$(COMPOSE_FILE)" ]; then \
		echo "Missing $(COMPOSE_FILE). Run 'make setup' first."; \
		exit 1; \
	fi
	@if ! $(DOCKER_COMPOSE_RUN) ps --status running | grep -q biblebot; then \
		echo "Container is not running. Run 'make run' first."; \
		exit 1; \
	fi
	@$(DOCKER_COMPOSE_RUN) exec biblebot /bin/bash || $(DOCKER_COMPOSE_RUN) exec biblebot /bin/sh

clean:
	@if [ ! -f "$(COMPOSE_FILE)" ]; then \
		echo "Missing $(COMPOSE_FILE). Nothing to clean."; \
		exit 0; \
	fi
	@echo "Removing containers and networks..."
	@$(DOCKER_COMPOSE_RUN) down --remove-orphans
