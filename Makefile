.PHONY: tt-bootstrap tt-start tt-health tt-deploy tt-stop tt-repair tt-flow tt-gate-drills op-map op-new op-plan op-initialize op-build lane-c-bundle lane-c-install-global lane-c-doctor

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

op-map:
	./scripts/op/opctl.sh /op-map-codebase --json-pretty

op-new:
	./scripts/op/opctl.sh /op-new-project --json-pretty

op-plan:
	./scripts/op/opctl.sh /op-plan --json-pretty

op-initialize:
	./scripts/op/opctl.sh /op-initialize --json-pretty

op-build:
	./scripts/op/opctl.sh /op-build --json-pretty

lane-c-bundle:
	python3 -m scripts.release.build_lane_c_bundle --repo-root $(PWD) --out-dir $(PWD)/dist --json-pretty

lane-c-install-global:
	python3 ./scripts/install/op_install.py --bundle-dir $(PWD)/dist/optimus-prime-$$(cat VERSION) --mode global --json-pretty

lane-c-doctor:
	python3 ./scripts/install/op_doctor.py --mode global --json-pretty
