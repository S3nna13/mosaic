.PHONY: help install lint test build docker push deploy

help:
	@echo "MOSAIC Developer Commands"
	@echo "  make install      — install package + dev deps in .venv"
	@echo "  make lint         — run black + ruff + mypy"
	@echo "  make test         — unit + integration + smoke"
	@echo "  make build        — build wheel + sdist"
	@echo "  make docker       — build docker image"
	@echo "  make push         — push docker image (requires registry login)"
	@echo "  make deploy       — kubectl apply -k k8s/overlays/prod"
	@echo "  make clean        — remove build artefacts"

install:
	python -m venv .venv
	. .venv/bin/activate && pip install -U pip
	. .venv/bin/activate && pip install -e '.[dev]'
	pre-commit install

lint:
	black --check src/mosaic tests
	ruff check src/mosaic tests
	mypy src/mosaic --strict --ignore-missing-imports

format:
	black src/mosaic tests
	ruff check --fix src/mosaic tests

test:
	pytest -x --tb=short --cov=mosaic --cov-report=term-missing
	pytest tests/smoke.py

build:
	pip install build
	rm -rf dist
	python -m build --sdist --wheel
	twine check dist/*

docker:
	docker build -t mosaic:latest -f Dockerfile .

push:
	docker tag mosaic:latest <your-registry>/mosaic:latest
	docker push <your-registry>/mosaic:latest

deploy:
	kubectl apply -k k8s/overlays/prod

clean:
	rm -rf .venv dist build *.egg-info .mypy_cache .ruff_cache .pytest_cache htmlcov
	find . -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
