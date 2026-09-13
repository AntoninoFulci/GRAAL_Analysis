PYTHON ?= python
GRAPHIFY ?= $(PYTHON) -m graphify
export PYTHONPATH := $(CURDIR)$(if $(PYTHONPATH),:$(PYTHONPATH))

.PHONY: help setup syntax test-root-free test validate-manifest observable-runs graph-update graph-query artifact-inventory verify

help:
	@echo "Targets: setup syntax test-root-free test validate-manifest observable-runs graph-update graph-query artifact-inventory verify"
	@echo "Use an interpreter compatible with external ROOT/PyROOT. verify is read-only and never starts farm processing."

setup:
	$(PYTHON) -m pip install --upgrade pip setuptools
	$(PYTHON) -m pip install -r requirements-dev.txt
	$(PYTHON) -m pip install -r requirements-graphify.txt
	$(PYTHON) -m pip install -e .

syntax:
	$(PYTHON) -c 'import subprocess; [compile(open(path, "rb").read(), path, "exec") for path in subprocess.check_output(["git", "ls-files", "*.py"], text=True).splitlines()]'
	bash -n run_pipeline.sh scripts/sync-wiki.sh

test-root-free:
	$(PYTHON) -m pytest -q 00_common/tests/test_build_artifact_inventory.py 00_common/tests/test_build_observable_run_database.py 00_common/tests/test_channels.py 00_common/tests/test_cross_sections.py 00_common/tests/test_observable_runs.py 00_common/tests/test_pairing.py 00_common/tests/test_repository_contract.py 00_common/tests/test_run_manifest.py 00_common/tests/test_strip_energy_flux.py 03_mc_simulation/tests/test_generator_physics.py 03_mc_simulation/tests/test_mc_status.py 04_bdt_training/tests/test_beam_spectrum.py 04_bdt_training/tests/test_build_background_features.py 04_bdt_training/tests/test_callbacks.py 04_bdt_training/tests/test_photon_loss.py 04_bdt_training/tests/test_train_bdt_stage1.py
	$(PYTHON) -m pytest -q 08_polarization/tests --ignore=08_polarization/tests/test_figure4_end_to_end.py --ignore=08_polarization/tests/test_root_events_integration.py

test:
	$(PYTHON) -m pytest -q

validate-manifest:
	$(PYTHON) scripts/build_run_manifest.py --validate config/run_manifest.csv

observable-runs:
	$(PYTHON) scripts/build_observable_run_database.py --manifest config/run_manifest.csv --strip-energy-dir results/strip_energy_flux --output-dir results/observable_runs

graph-update:
	$(GRAPHIFY) update .

graph-query:
	$(GRAPHIFY) query "$(QUERY)"

artifact-inventory:
	$(PYTHON) scripts/build_artifact_inventory.py --repo-root . --commit "$$(git rev-parse HEAD)" --output ARTIFACTS.json

verify: syntax validate-manifest test-root-free
	$(PYTHON) scripts/build_artifact_inventory.py --repo-root . --verify --inventory ARTIFACTS.json
	@git diff --check
