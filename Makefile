.PHONY: sanity sanity-alt check render-test render-compile render-smoke interaction-run bench bench-ci

sanity:
	./scripts/dev-sanity.sh

sanity-alt:
	ORCH_PORT=28010 UI_PORT=23000 ./scripts/dev-sanity.sh

check:
	python -m unittest discover -s orchestration-server/tests -p 'test_*.py'
	python -m unittest discover -s render-node/tests -p 'test_*.py'
	cd control-ui && npm run lint
	cd control-ui && npm run build

render-test:
	python -m unittest discover -s render-node/tests -p 'test_*.py'

render-compile:
	python -m compileall render-node/app

render-smoke:
	./scripts/render-smoke.sh

interaction-run:
	python interaction-engine/app/main.py

bench:
	python render-node/benchmarks/bench_gpu_pipeline.py --frames 200 --output bench-report.json

bench-ci:
	python render-node/benchmarks/bench_gpu_pipeline.py --frames 200 --output bench-report.json --ci
