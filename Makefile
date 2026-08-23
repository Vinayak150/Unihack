.PHONY: setup build-index profile enrich evaluate test demo clean docker-build docker-run

PY ?= python3
INPUT ?= data/raw/sample_1000_items_input.csv
OUTPUT ?= reports/enriched_output.xlsx

setup:
	pip install -e ".[dev]"
	cp -n .env.example .env || true
	$(MAKE) build-index

build-index:
	$(PY) scripts/build_reference_data.py

profile:
	$(PY) -m app.cli profile --input $(INPUT)

enrich:
	$(PY) -m app.cli enrich --input $(INPUT) --output $(OUTPUT) --report-dir reports

evaluate:
	$(PY) -m app.cli evaluate --input $(INPUT) --report-dir reports

test:
	$(PY) -m pytest -q

demo:
	$(PY) -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload

docker-build:
	docker build -t unilog-product-intelligence .

docker-run:
	docker compose up --build

clean:
	rm -rf reports/*.json reports/*.csv reports/*.md data/cache/uploads
	find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
