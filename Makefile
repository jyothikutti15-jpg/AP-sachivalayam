.PHONY: help setup run test seed embed lint clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## First-time setup: install deps, copy env, start services
	cp -n .env.example .env || true
	docker-compose up -d
	@echo "Waiting for services..."
	sleep 5
	docker-compose exec app python scripts/seed_db.py
	@echo "Setup complete! Visit http://localhost:8000/docs"

run: ## Start all services
	docker-compose up -d

run-dev: ## Start with live reload
	docker-compose up

stop: ## Stop all services
	docker-compose down

seed: ## Seed database with schemes, FAQs, form templates
	docker-compose exec app python scripts/seed_db.py

embed: ## Generate embeddings for RAG
	docker-compose exec app python scripts/generate_embeddings.py

embed-stats: ## Show embedding statistics
	docker-compose exec app python scripts/generate_embeddings.py --stats

test: ## Run all tests
	docker-compose exec app pytest tests/ -v

test-fast: ## Run tests without slow integration tests
	docker-compose exec app pytest tests/ -v -m "not slow"

lint: ## Run linter
	docker-compose exec app ruff check app/ tests/

lint-fix: ## Auto-fix lint issues
	docker-compose exec app ruff check --fix app/ tests/

validate-schemes: ## Validate all scheme JSON files
	docker-compose exec app python scripts/scrape_schemes.py --validate

logs: ## Show app logs
	docker-compose logs -f app

logs-celery: ## Show Celery worker logs
	docker-compose logs -f celery-worker

health: ## Check service health
	curl -s http://localhost:8000/api/v1/health | python -m json.tool

migrate: ## Run database migrations
	docker-compose exec app alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create msg="add xyz")
	docker-compose exec app alembic revision --autogenerate -m "$(msg)"

clean: ## Remove all containers and volumes
	docker-compose down -v
	rm -rf __pycache__ .pytest_cache .ruff_cache
