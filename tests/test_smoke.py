"""Smoke test so the CI pipeline has something to run before any code exists."""

import credence


def test_package_imports() -> None:
    assert credence.__version__
