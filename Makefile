# Convenience targets for the serving layer (Part 12). The pipeline itself is
# driven by DVC, not make.
#
# Python is pinned to 3.11 on purpose: it is the interpreter the pipeline
# (requirements.txt) and CI are verified on, and the system default here is
# newer (3.14). This keeps .venv-serve aligned with .venv; think twice before
# parameterizing this.
SERVE_PY ?= .venv-serve/bin/python
API_URL ?= http://127.0.0.1:8000
PORT ?= 8000

.PHONY: serve-venv api ui bundle test-api

serve-venv:
	python3.11 -m venv .venv-serve
	$(SERVE_PY) -m pip install --upgrade pip
	$(SERVE_PY) -m pip install -r src/api/requirements.txt -r app/requirements.txt

api:
	$(SERVE_PY) -m uvicorn src.api.main:app --host 0.0.0.0 --port $(PORT) --reload

ui:
	LANTERN_API_URL=$(API_URL) $(SERVE_PY) -m streamlit run app/streamlit_app.py

bundle:
	$(SERVE_PY) -m src.api.build_bundle --force

test-api:
	$(SERVE_PY) -m pytest -q tests/test_api.py
