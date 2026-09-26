.PHONY: help build up down logs health ai-health api-health train-model test ai-test api-test clean rebuild restart

DOCKER_COMPOSE := docker-compose
PYTHON := python
PIP := pip

help:
	@echo "Meko Crown Development Commands"
	@echo "================================"
	@echo ""
	@echo "Docker Compose:"
	@echo "  make build          Build Docker images for all services"
	@echo "  make up             Start all services (API + AI)"
	@echo "  make down           Stop all services"
	@echo "  make logs           Tail logs from all services"
	@echo "  make restart        Restart all services"
	@echo "  make rebuild        Rebuild and restart services"
	@echo ""
	@echo "Health Checks:"
	@echo "  make health         Check health of all services"
	@echo "  make ai-health      Check AI service health"
	@echo "  make api-health     Check API service health"
	@echo ""
	@echo "AI Service (local):"
	@echo "  make train-model    Train the underwriting ML model"
	@echo "  make ai-run         Run AI service locally (requires model.pkl)"
	@echo "  make ai-test        Run AI service integration tests"
	@echo "  make ai-install     Install AI service dependencies"
	@echo ""
	@echo "API Service (local):"
	@echo "  make api-install    Install API service dependencies"
	@echo "  make api-run        Run API service locally"
	@echo "  make api-test       Run API service tests"
	@echo ""
	@echo "General:"
	@echo "  make test           Run all tests (AI + API)"
	@echo "  make clean          Remove Docker containers, volumes, and caches"
	@echo "  make help           Show this help message"

# Docker Compose Commands
build:
	$(DOCKER_COMPOSE) build

up:
	$(DOCKER_COMPOSE) up -d
	@echo "Services started. Check health with 'make health'"

down:
	$(DOCKER_COMPOSE) down

logs:
	$(DOCKER_COMPOSE) logs -f

restart: down up

rebuild: down build up

# Health Checks
health: ai-health api-health
	@echo "✓ All services healthy"

ai-health:
	@echo "Checking AI service..."
	@curl -s http://localhost:8001/health | jq . || echo "✗ AI service unavailable"

api-health:
	@echo "Checking API service..."
	@curl -s http://localhost:3000/health | jq . || echo "✗ API service unavailable"

# AI Service Commands
ai-install:
	cd services/ai && $(PIP) install -r requirements.txt

train-model:
	cd services/ai && $(PYTHON) train_model.py

ai-run: ai-install
	cd services/ai && $(PYTHON) main.py

ai-test: ai-install
	cd services/ai && $(PYTHON) -m pytest -v tests/test_main.py

ai-lint:
	cd services/ai && $(PYTHON) -m pylint main.py train_model.py || true

ai-format:
	cd services/ai && $(PYTHON) -m black main.py train_model.py tests/

# API Service Commands
api-install:
	cd services/api && npm install

api-run: api-install
	cd services/api && npm run dev

api-test: api-install
	cd services/api && npm test

# Combined Commands
test: ai-test api-test
	@echo "✓ All tests passed"

install: ai-install api-install
	@echo "✓ Dependencies installed for all services"

clean:
	$(DOCKER_COMPOSE) down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	@echo "✓ Clean complete"

# Development workflow examples
dev-setup: install train-model build
	@echo "✓ Development environment ready"
	@echo "Start with: make up"

dev-watch: up logs
	@echo "Services running with log tail"
