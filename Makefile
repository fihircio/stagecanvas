.PHONY: sanity sanity-alt

sanity:
	./scripts/dev-sanity.sh

sanity-alt:
	ORCH_PORT=28010 UI_PORT=23000 ./scripts/dev-sanity.sh
