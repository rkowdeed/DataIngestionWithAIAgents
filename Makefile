.PHONY: install db-up db-down test lint fmt run-sample

install:
	pip install -r requirements.txt

db-up:
	docker compose -f docker/docker-compose.yml up -d

db-down:
	docker compose -f docker/docker-compose.yml down -v

test:
	pytest -v --cov=etl_platform --cov-report=term-missing

lint:
	ruff check etl_platform tests

fmt:
	ruff check --fix etl_platform tests

run-sample:
	python -m etl_platform.aws.glue_job_entrypoint --pipeline_name plasma_etch_wafer_ingest
