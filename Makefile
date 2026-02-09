.PHONY: setup run run-api run-worker test lint migrate docker-build

PY := $(if $(wildcard ./.venv/bin/python),./.venv/bin/python,python3)

setup:
	python3 scripts/setup_env.py

migrate:
	python3 scripts/migrate_db.py

run:
	python3 scripts/run_pipeline.py

run-api:
	python3 scripts/run_api.py

run-worker:
	python3 scripts/run_worker.py

test:
	$(PY) scripts/run_tests.py

lint:
	$(PY) -m py_compile apps/api/main.py apps/api/utils.py apps/api/deps.py apps/api/schemas.py apps/api/cache.py apps/api/rate_limit.py apps/api/routes/health.py apps/api/routes/auth.py apps/api/routes/activities.py apps/api/routes/insights.py apps/api/routes/segments.py services/processing/pipeline.py scripts/run_pipeline.py scripts/run_api.py scripts/run_worker.py scripts/run_tests.py scripts/worker_healthcheck.py

docker-build:
	./scripts/verify_docker.sh
