.PHONY: tt-bootstrap tt-start tt-health tt-deploy tt-stop tt-repair tt-flow tt-gate-drills

tt-bootstrap:
	./scripts/test-train/ttctl.sh bootstrap

tt-start:
	./scripts/test-train/ttctl.sh start

tt-health:
	./scripts/test-train/ttctl.sh health

tt-deploy:
	./scripts/test-train/ttctl.sh deploy

tt-stop:
	./scripts/test-train/ttctl.sh stop

tt-repair:
	./scripts/test-train/ttctl.sh repair

tt-flow:
	./scripts/test-train/ttctl.sh flow

tt-gate-drills:
	./scripts/test-train/run-gate-drills.sh
