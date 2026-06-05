"""
Pytest fixtures shared across the test suite.

A fixture is a reusable object/state set up before tests run and
torn down afterwards. Fixtures defined here are automatically
discovered by pytest in any test_*.py file in this folder.
"""

import pytest

from app.services.system_monitor import SystemMonitor


@pytest.fixture(scope="module")
def monitor():
    """
    Provide a single SystemMonitor instance reused across all tests
    in the same module.

    scope='module' = created once per test file (efficient because
    psutil calls have a small overhead).
    """
    return SystemMonitor()