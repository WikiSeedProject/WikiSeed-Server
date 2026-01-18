# WikiSeed Makefile
# Common development tasks

.PHONY: help install test lint format clean dev-up dev-down dev-logs db-init db-shell db-reset

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies and setup development environment
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pre-commit install
	@echo "✓ Development environment ready"

test:  ## Run tests with coverage
	pytest -v --cov=src --cov-report=html --cov-report=term

test-fast:  ## Run tests without coverage
	pytest -v -x

test-small-wiki:  ## Run small wiki mode end-to-end test
	pytest tests/small_wiki_mode/ -v -s

lint:  ## Run linters (ruff, mypy)
	ruff check src/ tests/
	mypy src/

format:  ## Format code with black and ruff
	black src/ tests/
	ruff check --fix src/ tests/

clean:  ## Clean up generated files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	@echo "✓ Cleaned up generated files"

dev-up:  ## Start development environment
	docker compose -f docker-compose.dev.yml up -d
	@echo "✓ Development environment started"
	@echo "Monitor UI: http://localhost:8000"
	@echo "qBittorrent: http://localhost:8080"

dev-down:  ## Stop development environment
	docker compose -f docker-compose.dev.yml down
	@echo "✓ Development environment stopped"

dev-logs:  ## Tail development logs
	docker compose -f docker-compose.dev.yml logs -f

db-init:  ## Initialize database
	python scripts/init_db.py
	@echo "✓ Database initialized"

db-shell:  ## Open database shell
	sqlite3 data/db/jobs.db

db-reset:  ## Reset database (WARNING: deletes all data!)
	@echo "WARNING: This will delete all data in the database!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -f data/db/jobs.db; \
		python scripts/init_db.py; \
		echo "✓ Database reset complete"; \
	else \
		echo "Cancelled"; \
	fi

build:  ## Build Docker containers
	docker compose build

prod-up:  ## Start production environment
	docker compose up -d
	@echo "✓ Production environment started"

prod-down:  ## Stop production environment
	docker compose down

prod-logs:  ## Tail production logs
	docker compose logs -f

status:  ## Show system status
	@echo "=== Docker Containers ==="
	@docker compose ps 2>/dev/null || echo "Not running"
	@echo ""
	@echo "=== Disk Usage ==="
	@du -sh data/* 2>/dev/null || echo "No data directory"
	@echo ""
	@echo "=== Database Stats ==="
	@sqlite3 data/db/jobs.db "SELECT job_type, status, COUNT(*) as count FROM jobs GROUP BY job_type, status;" 2>/dev/null || echo "No database"
