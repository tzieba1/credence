"""Measure the extraction against the labelled set.

`pytest -m eval` runs it. Recorded mode replays saved API responses through
the real extraction code and costs nothing; `--live` calls the API, rewrites
the fixtures and writes a results file.
"""
