PY ?= .venv/bin/python
STEPS = 01_fetch_targets 02_fetch_earth 03_reproject 04_patches 05_features \
        06_embed 07_index 08_query 08b_usual_sites 09_environment 09b_lighting 10_validate 11_export 11c_simulated_craters
CORE_STEPS = 03_reproject 04_patches 05_features 06_embed 07_index 08_query

.PHONY: setup pipeline pipeline-small res90 test web web-build clean-small

setup:
	uv venv --python 3.11 .venv
	uv pip install --python $(PY) -r requirements.txt
	cd web && npm ci

## Full run: every target and region, exports to web/public/data
pipeline:
	@for s in $(STEPS); do echo "== $$s"; RG_PROFILE=full $(PY) pipeline/$$s.py || exit 1; done

## Smoke run: 1 target, 2 regions, exports to data/small/export (under 3 minutes)
pipeline-small:
	@for s in $(STEPS); do echo "== $$s"; RG_PROFILE=small $(PY) pipeline/$$s.py || exit 1; done

## 90 m robustness rerun used by 10_validate.py (V3)
res90:
	@for s in $(CORE_STEPS); do echo "== $$s"; RG_PROFILE=res90 $(PY) pipeline/$$s.py || exit 1; done

test:
	$(PY) -m pytest -q

web:
	cd web && npm run dev

web-build:
	cd web && npm run typecheck && npm run build

clean-small:
	rm -rf data/small
