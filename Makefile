# Matrix BibleBot container workflow

DOCKER_COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")
BIBLEBOT_HOST_HOME ?= $(HOME)/.config/matrix-biblebot
COMPOSE_FILE ?= docker-compose.yaml
SOURCE_OVERRIDE ?= docker-compose.source.yaml
SAMPLE_CONFIG := src/biblebot/tools/sample_config.yaml
COMPOSE_ENV = env BIBLEBOT_HOST_HOME="$(BIBLEBOT_HOST_HOME)" UID="$(shell id -u)" GID="$(shell id -g)
COMPOSE = $(COMPOSE_ENV) $(DOCKER_COMPOSE) -f "$(COMPOSE_FILE)" $(if $(wildcard $(SOURCE_OVERRIDE)),-f "$(SOURCE_OVERRIDE)")

.PHONY: help setup use-source use-prebuilt config-check auth-login auth-status pull build run stop logs clean

help:
	@printf '%s\n' \
	  "make setup         Create runtime and prebuilt Compose files" \
	  "make use-source    Enable the local source-build override" \
	  "make use-prebuilt  Remove the source-build override" \
	  "make pull          Pull the published image" \
	  "make build         Build the local source image" \
	  "make auth-login    Save Matrix credentials under the runtime home" \
	  "make config-check  Validate configuration in a one-shot container" \
	  "make run           Start BibleBot" \
	  "make logs          Follow logs" \
	  "make stop          Stop BibleBot" \
	  "make clean         Remove the Compose deployment"

setup:
	@mkdir -p "$(BIBLEBOT_HOST_HOME)"
	@if [ ! -f "$(BIBLEBOT_HOST_HOME)/config.yaml" ]; then cp "$(SAMPLE_CONFIG)" "$(BIBLEBOT_HOST_HOME)/config.yaml"; fi
	@if [ ! -f "$(COMPOSE_FILE)" ]; then cp sample-docker-compose.yaml "$(COMPOSE_FILE)"; fi
	@printf 'Runtime: %s\nConfig: %s/config.yaml\nNext: edit the config, then run make auth-login && make run\n' "$(BIBLEBOT_HOST_HOME)" "$(BIBLEBOT_HOST_HOME)"

use-source: setup
	@cp sample-docker-compose.source.yaml "$(SOURCE_OVERRIDE)"
	@echo "Source build enabled."

use-prebuilt: setup
	@rm -f "$(SOURCE_OVERRIDE)"
	@echo "Prebuilt image enabled."

pull:
	@$(COMPOSE) pull

build:
	@if [ ! -f "$(SOURCE_OVERRIDE)" ]; then echo "Run 'make use-source' first."; exit 1; fi
	@$(COMPOSE) build

config-check:
	@$(COMPOSE) run --rm biblebot biblebot config check

auth-login:
	@$(COMPOSE) run --rm biblebot biblebot auth login

auth-status:
	@$(COMPOSE) run --rm biblebot biblebot auth status

run:
	@$(COMPOSE) up -d

stop:
	@$(COMPOSE) stop

logs:
	@$(COMPOSE) logs -f

clean:
	@$(COMPOSE) down --remove-orphans
