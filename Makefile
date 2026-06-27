.PHONY: install test lint fmt run dev

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

lint:
	ruff check app/ tests/
	ruff format --check app/ tests/

fmt:
	ruff check app/ tests/ --fix
	ruff format app/ tests/

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev: install
	uvicorn app.main:app --reload
