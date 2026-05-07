.PHONY: install run test test-frontend lint build serve verify-quotes

PYTHON ?= python3
VENV ?= .venv

install:
	@echo "Creating virtualenv and installing backend/frontend dependencies"
	$(PYTHON) -m venv $(VENV)
	. $(VENV)/bin/activate && pip install --upgrade pip
	. $(VENV)/bin/activate && pip install -e backend -r backend/requirements-dev.txt
	npm --prefix frontend install

run:
	@echo "Running backend and frontend dev servers on loopback"
	. $(VENV)/bin/activate && PYTHONPATH=backend/src uvicorn podsum.main:app --host 127.0.0.1 --port 8000 --reload & npm --prefix frontend run dev -- --host 127.0.0.1

test:
	@echo "Running backend pytest with domain coverage gate"
	. $(VENV)/bin/activate && PYTHONPATH=backend/src pytest backend/tests --cov=backend/src/podsum/domain --cov-fail-under=80

test-frontend:
	@echo "Running frontend Vitest"
	npm --prefix frontend run test

lint:
	@echo "Running backend Ruff and frontend TypeScript lint"
	. $(VENV)/bin/activate && ruff check backend/src backend/tests
	npm --prefix frontend run lint

build:
	@echo "Building frontend SPA into frontend/dist"
	npm --prefix frontend run build

serve:
	@echo "Serving built SPA from FastAPI at 127.0.0.1:8000"
	. $(VENV)/bin/activate && PYTHONPATH=backend/src uvicorn podsum.main:app --host 127.0.0.1 --port 8000

verify-quotes:
	@echo "Verifying stored quotes against transcripts"
	. $(VENV)/bin/activate && PYTHONPATH=backend/src python scripts/verify_quotes.py
