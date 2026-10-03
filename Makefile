.DEFAULT_GOAL := aide
COMPOSE := docker compose
NODE_IMAGE := node:22-alpine

.PHONY: aide env up down logs ps migrate test test-back test-front lint format seed purge clean

aide: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

env: ## Crée .env à partir de .env.example s'il n'existe pas
	@test -f .env || cp .env.example .env

up: env ## Construit et lance toute la stack (http://localhost:3000)
	$(COMPOSE) up -d --build
	@echo "Interface : http://localhost:3000  |  API : http://localhost:8000/docs"

down: ## Arrête la stack
	$(COMPOSE) down

logs: ## Suit les logs de l'API et du worker
	$(COMPOSE) logs -f api worker

ps: ## État des services
	$(COMPOSE) ps

migrate: ## Applique les migrations Alembic
	$(COMPOSE) run --rm api alembic upgrade head

test: test-back test-front ## Lance tous les tests (sans clé API ni réseau)

test-back: env ## Tests back-end (pytest + couverture) dans le conteneur
	$(COMPOSE) up -d --wait db redis
	$(COMPOSE) run --rm --build -e LLM_PROVIDER=fake -e COHERE_API_KEY= api pytest

test-front: ## Tests front-end (Vitest) dans un conteneur Node
	docker run --rm -v "$(CURDIR)/frontend:/app" -v /app/node_modules -w /app $(NODE_IMAGE) \
		sh -c "npm ci --no-audit --no-fund && npm run typecheck && npm test"

lint: env ## ruff + mypy
	$(COMPOSE) run --rm --no-deps api sh -c "ruff check . && ruff format --check . && mypy app"

format: env ## Formate le code Python
	$(COMPOSE) run --rm --no-deps -v "$(CURDIR)/backend:/app" api sh -c "ruff format . && ruff check --fix ."

seed: ## Charge 5 dossiers de démonstration (phase 10)
	$(COMPOSE) exec api python -m scripts.seed

purge: ## Purge immédiate (dossiers expirés selon RETENTION_JOURS, fichiers orphelins)
	$(COMPOSE) exec api python -m app.workers.purge

clean: ## Arrête la stack et supprime les volumes (données effacées)
	$(COMPOSE) down -v
