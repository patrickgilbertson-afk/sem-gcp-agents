.PHONY: install test lint format run docker-build docker-up clean deploy

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --cov=src --cov-report=term-missing

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

lint:
	ruff check src/ tests/
	mypy src/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

run:
	uvicorn src.main:app --reload --port 8080

docker-build:
	docker build -t sem-gcp-agents:latest .

docker-up:
	docker-compose up --build

docker-down:
	docker-compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true

terraform-init:
	cd terraform && terraform init

terraform-plan:
	cd terraform && terraform plan

terraform-apply:
	cd terraform && terraform apply

deploy:
	./scripts/deploy.sh
