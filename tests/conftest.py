"""
Pytest fixtures shared across the test suite.

A fixture is a reusable object/state set up before tests run and
torn down afterwards. Fixtures defined here are automatically
discovered by pytest in any test_*.py file in this folder.
"""

import pytest

from app import create_app
from app.extensions import db as _db
from app.services.system_monitor import SystemMonitor
from app.models.user import User
from app.utils.security import hash_password


# ============================================================
# SystemMonitor (Bloco 3)
# ============================================================

@pytest.fixture(scope="module")
def monitor():
    """
    Provide a single SystemMonitor instance reused across all tests
    in the same module.

    scope='module' = created once per test file (efficient because
    psutil calls have a small overhead).
    """
    return SystemMonitor()


# ============================================================
# Flask app + DB (for API integration tests)
# ============================================================

@pytest.fixture(scope="function")
def app():
    """
    Create a fresh Flask app with TestingConfig for each test.

    Why function-scoped? Each test gets a clean in-memory database,
    guaranteeing zero state leakage between tests.
    """
    flask_app = create_app("testing")

    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    """Flask test client — for sending HTTP requests in tests."""
    return app.test_client()


@pytest.fixture(scope="function")
def db_session(app):
    """Direct DB access inside a test (for seeding data)."""
    return _db.session


# ============================================================
# Users + JWT auth helpers
# ============================================================

@pytest.fixture(scope="function")
def test_user(db_session):
    """Create a regular 'support' user and return it."""
    user = User(
        email="tester@itmonitor.com",
        password_hash=hash_password("TestPass1!"),
        full_name="Test User",
        role="support",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture(scope="function")
def admin_user(db_session):
    """Create an 'admin' user and return it."""
    user = User(
        email="admin@itmonitor.com",
        password_hash=hash_password("AdminPass1!"),
        full_name="Admin User",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture(scope="function")
def auth_headers(client, test_user):
    """
    Log in as the regular user and return a dict of HTTP headers
    ready to attach to authenticated requests.

    Usage:
        client.post("/api/v1/incidents", json=payload, headers=auth_headers)
    """
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "tester@itmonitor.com", "password": "TestPass1!"},
    )
    token = response.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def admin_headers(client, admin_user):
    """Log in as admin and return auth headers."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@itmonitor.com", "password": "AdminPass1!"},
    )
    token = response.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}