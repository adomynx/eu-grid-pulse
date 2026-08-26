.PHONY: up down run test-token

up:
	docker compose up -d

down:
	docker compose down

run:
	python -m src.pipeline

test-token:
	python -m src.ingest.extract_entsoe --smoke-test
