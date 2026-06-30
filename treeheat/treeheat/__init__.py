"""treeheat — tree thermal-safety simulation pipeline (v1).

Layered, config-driven pipeline:
    config -> io -> radiance -> physics(engines) -> risk -> viz

Orchestration core (job spec, runner, provenance, run-state) sits above the
pipeline stages; CLI and api.py are its consumers.
"""
from treeheat import api

__version__ = "0.1.0"

__all__ = ["__version__", "api", "run", "status", "load_analysis"]

run = api.run
status = api.status
load_analysis = api.load_analysis
