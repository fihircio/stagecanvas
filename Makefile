.PHONY: sanity sanity-alt check render-test render-compile

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
