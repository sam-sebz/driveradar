# DriveRadar tasks. On Windows without make, use: .\scripts\dev.ps1 <target>
PYTHON ?= python
BACKEND := backend
FRONTEND := frontend

.PHONY: help setup up down logs test test-backend test-frontend lint seed eval smoke samples

help:
	@echo "make setup   - install backend (venv) and frontend dev dependencies"
	@echo "make up      - build and start db + backend + frontend (waits until healthy)"
	@echo "make down    - stop the stack"
	@echo "make test    - backend + frontend tests with coverage"
	@echo "make lint    - ruff, mypy, eslint, tsc"
	@echo "make seed    - load demo data into the running stack"
	@echo "make eval    - extraction accuracy on labelled notices -> eval/results.md"
	@echo "make smoke   - end-to-end check against the running stack"

setup:
	cd $(BACKEND) && $(PYTHON) -m pip install -r requirements-dev.txt
	cd $(FRONTEND) && npm ci

.env:
	cp .env.example .env

up: .env
	docker compose up --build -d --wait
	@echo "API: http://localhost:8000/docs   App: http://localhost:5173"

down:
	docker compose down

logs:
	docker compose logs -f backend

test: test-backend test-frontend

test-backend:
	cd $(BACKEND) && $(PYTHON) -m pytest --cov=app --cov-report=term-missing --cov-fail-under=70
	cd $(BACKEND) && $(PYTHON) -m coverage report --include="app/domain/*" --fail-under=70

test-frontend:
	cd $(FRONTEND) && npm run test:coverage

lint:
	cd $(BACKEND) && $(PYTHON) -m ruff check . && $(PYTHON) -m ruff format --check . && $(PYTHON) -m mypy app tests
	cd $(FRONTEND) && npm run lint && npm run typecheck

seed:
	docker compose exec backend python -m app.seed

eval:
	cd $(BACKEND) && $(PYTHON) ../eval/run_eval.py

smoke:
	$(PYTHON) scripts/smoke.py

samples:
	cd $(BACKEND) && $(PYTHON) scripts/make_samples.py && $(PYTHON) ../eval/make_heldout.py
