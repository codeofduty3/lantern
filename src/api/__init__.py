"""LANTERN serving layer: a read-only FastAPI backend and its Streamlit frontend.

``src.api.main`` is the ASGI app that exposes the pipeline outputs (provenance
blocks, Markdown, tables, XBRL facts, metrics) as a JSON API with interactive
Swagger docs at ``/docs``. ``app/streamlit_app.py`` is the UI that consumes it.
"""
