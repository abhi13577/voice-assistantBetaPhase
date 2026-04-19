.PHONY: help install clean test lint format run deploy run-docker

help:
	@echo "Voice Support Engine - Development Commands"
	@echo "=============================================="
	@echo "Setup:"
	@echo "  make install          - Install dependencies"
	@echo "  make install-dev      - Install dev dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make run              - Run dev server with auto-reload"
	@echo "  make run-docker       - Run with Docker Compose"
	@echo "  make redis            - Start Redis in Docker"
	@echo ""
	@echo "Quality:"
	@echo "  make lint             - Run all linting (flake8, black, isort)"
	@echo "  make format           - Auto-format code (black, isort)"
	@echo "  make test             - Run all tests with coverage"
	@echo "  make test-unit        - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-coverage    - Generate HTML coverage report"
	@echo ""
	@echo "Docker & Kubernetes:"
	@echo "  make build-docker     - Build Docker image"
	@echo "  make deploy-k8s       - Deploy to Kubernetes"
	@echo "  make deploy-k8s-dev   - Deploy to dev namespace"
	@echo "  make logs-k8s         - Stream logs from K8s"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            - Remove cache and build artifacts"
	@echo "  make clean-all        - Remove everything including venv"

# Setup
install:
	pip install -r requirements-backend.txt

install-dev:
	pip install -r requirements-backend.txt
	pip install pytest pytest-asyncio pytest-cov black flake8 isort bandit safety

# Development
run:
	export ENV=dev && \
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-docker:
	docker-compose up -d redis
	docker build -t voice-support-engine:latest .
	docker run -d \
		--name voice-support \
		--network host \
		-e ENV=dev \
		-e REDIS_HOST=localhost \
		-v $(PWD)/app:/app/app \
		voice-support-engine:latest

redis:
	docker run -d -p 6379:6379 --name redis-dev redis:7-alpine

redis-stop:
	docker stop redis-dev && docker rm redis-dev

redis-cli:
	docker exec -it redis-dev redis-cli

# Quality
lint:
	@echo "Running Black format check..."
	black --check app/ tests/
	@echo "Running isort import check..."
	isort --check-only app/ tests/
	@echo "Running Flake8 linting..."
	flake8 app/ tests/ --max-line-length=120 --extend-ignore=E203
	@echo "Running Bandit security scan..."
	bandit -r app/ -ll || true

format:
	@echo "Running Black formatter..."
	black app/ tests/
	@echo "Running isort..."
	isort app/ tests/

test:
	@echo "Running all tests with coverage..."
	pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html

test-unit:
	@echo "Running unit tests..."
	pytest tests/ -v -k "not integration" --tb=short

test-integration:
	@echo "Running integration tests..."
	pytest tests/test_integration_api.py -v --tb=short

test-coverage:
	pytest tests/ --cov=app --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

test-watch:
	pytest-watch tests/ -- -v

# Docker & Kubernetes
build-docker:
	@echo "Building Docker image..."
	docker build -t voice-support-engine:latest .
	docker tag voice-support-engine:latest voice-support-engine:$(shell date +%Y%m%d-%H%M%S)

push-docker:
	@echo "Pushing to registry..."
	docker tag voice-support-engine:latest docker.io/yourusername/voice-support-engine:latest
	docker push docker.io/yourusername/voice-support-engine:latest

deploy-k8s:
	@echo "Deploying to Kubernetes..."
	kubectl apply -f k8s/00-namespace-config-redis.yaml
	sleep 5
	kubectl apply -f k8s/01-deployment.yaml
	kubectl apply -f k8s/02-service-rbac.yaml
	kubectl apply -f k8s/03-ingress-network-policy.yaml
	kubectl apply -f k8s/04-hpa-pdb-priority.yaml
	kubectl apply -f k8s/05-monitoring.yaml

deploy-k8s-dev:
	@echo "Deploying to Kubernetes dev namespace..."
	kubectl create namespace voice-support-dev || true
	kubectl apply -f k8s/01-deployment.yaml -n voice-support-dev

logs-k8s:
	kubectl logs -n voice-support -f -l app=voice-support-engine --all-containers=true

pods-k8s:
	kubectl get pods -n voice-support -o wide

endpoints-k8s:
	kubectl get endpoints -n voice-support voice-support-engine

port-forward-app:
	@echo "Forwarding localhost:8000 to voice-support-engine:8000"
	kubectl port-forward -n voice-support svc/voice-support-engine 8000:80

port-forward-prometheus:
	@echo "Forwarding localhost:9090 to prometheus:9090"
	kubectl port-forward -n voice-support svc/prometheus 9090:9090

port-forward-jaeger:
	@echo "Forwarding localhost:16686 to jaeger:16686"
	kubectl port-forward -n voice-support svc/jaeger-collector 16686:16686

# Cleanup
clean:
	@echo "Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info/ htmlcov/ .coverage
	docker-compose down -v 2>/dev/null || true

clean-all: clean
	@echo "Removing virtual environment..."
	rm -rf venv/

# Utilities
check-health:
	curl -s http://localhost:8000/health | jq .

check-metrics:
	curl -s http://localhost:8000/metrics | head -20

info:
	@echo "Python version:"
	python --version
	@echo ""
	@echo "Dependencies installed:"
	pip list | grep -E "fastapi|pydantic|redis|prometheus|pytest"
