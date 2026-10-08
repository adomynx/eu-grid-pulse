.PHONY: install run dagster export test-token

install:        ## install dependencies into the active environment
	pip install -r requirements.txt

run:            ## run the whole pipeline (ingest -> dbt build -> dashboard -> export)
	python -m src.run_pipeline

dagster:        ## launch the Dagster UI (http://localhost:3000)
	dagster dev -m src.dagster_defs

export:         ## refresh the Power BI data exports from the marts
	python -m src.export_powerbi

test-token:     ## confirm the ENTSO-E token (or synthetic fallback) works
	python -m src.ingest.extract_entsoe --smoke-test
