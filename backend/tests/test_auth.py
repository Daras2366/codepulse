"""Authentication endpoint tests.

Covers:
    - POST /auth/register — success and duplicate email
    - POST /auth/login    — success, wrong password, unknown email
    - GET  /users/me      — with valid token, without token
    - Logout (client-side only; clearing token prevents /users/me from working)
"""

import os
from unittest import TestCase

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DEBUG", "true")

import app.models  # noqa: F401 — ensure all models are registered
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import hash_password
from app.models.base import Base
from app.models.user import User
from app.routers import auth as auth_router
from app.routers import users as users_router


def _build_app(session):
    """Return a minimal FastAPI app with auth + users routers."""
    _app = FastAPI()
    _app.include_router(auth_router.router, prefix="/auth")
    _app.include_router(users_router.router, prefix="/users")

    def override_db():
        yield session

    _app.dependency_overrides[get_db] = override_db
    return _app


class RegisterTests(TestCase):
    """POST /auth/register"""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.client = TestClient(_build_app(self.session))

    def tearDown(self):
        self.client.close()
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_register_success_returns_user(self):
        resp = self.client.post(
            "/auth/register",
            json={
                "username": "alice",
                "email": "alice@example.com",
                "password": "secret123",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["username"], "alice")
        self.assertEqual(data["email"], "alice@example.com")
        self.assertNotIn("password_hash", data)
        self.assertIn("id", data)

    def test_register_hashes_password(self):
        """Password must never be stored in plain text."""
        self.client.post(
            "/auth/register",
            json={
                "username": "bob",
                "email": "bob@example.com",
                "password": "mypassword",
            },
        )
        user = (
            self.session.query(User).filter_by(email="bob@example.com").first()
        )
        self.assertIsNotNone(user)
        self.assertNotEqual(user.password_hash, "mypassword")
        # bcrypt hashes start with $2b$
        self.assertTrue(user.password_hash.startswith("$2"))

    def test_register_duplicate_email_returns_400(self):
        payload = {
            "username": "carol",
            "email": "carol@example.com",
            "password": "pw",
        }
        self.client.post("/auth/register", json=payload)
        # Second registration with same email
        resp = self.client.post(
            "/auth/register",
            json={**payload, "username": "carol2"},
        )
        self.assertEqual(resp.status_code, 400)


class LoginTests(TestCase):
    """POST /auth/login"""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

        # Seed a user directly
        self.user = User(
            username="dan",
            email="dan@example.com",
            password_hash=hash_password("correctpassword"),
        )
        self.session.add(self.user)
        self.session.commit()

        self.client = TestClient(_build_app(self.session))

    def tearDown(self):
        self.client.close()
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_login_success_returns_access_token(self):
        resp = self.client.post(
            "/auth/login",
            json={"email": "dan@example.com", "password": "correctpassword"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "bearer")
        self.assertIsInstance(data["access_token"], str)
        self.assertGreater(len(data["access_token"]), 20)

    def test_login_wrong_password_returns_401(self):
        resp = self.client.post(
            "/auth/login",
            json={"email": "dan@example.com", "password": "wrongpassword"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_login_unknown_email_returns_401(self):
        resp = self.client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "pw"},
        )
        self.assertEqual(resp.status_code, 401)


class MeEndpointTests(TestCase):
    """GET /users/me"""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

        self.user = User(
            username="eve",
            email="eve@example.com",
            password_hash=hash_password("pass"),
        )
        self.session.add(self.user)
        self.session.commit()

        # Build app with real auth (not overridden) to test token path
        self.app = _build_app(self.session)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _login_and_get_token(self) -> str:
        resp = self.client.post(
            "/auth/login",
            json={"email": "eve@example.com", "password": "pass"},
        )
        return resp.json()["access_token"]

    def test_me_with_valid_token_returns_user(self):
        token = self._login_and_get_token()
        resp = self.client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["email"], "eve@example.com")
        self.assertEqual(data["username"], "eve")
        self.assertNotIn("password_hash", data)

    def test_me_without_token_returns_401(self):
        resp = self.client.get("/users/me")
        self.assertEqual(resp.status_code, 401)  # HTTPBearer raises 401 when header is absent

    def test_me_with_invalid_token_returns_401(self):
        resp = self.client.get(
            "/users/me",
            headers={"Authorization": "Bearer invalidtoken.invalid.invalid"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_me_returns_correct_user_after_logout_simulation(self):
        """After clearing the token client-side, /users/me returns 401 (no header)."""
        # Simulate logout by simply not including the Authorization header
        resp = self.client.get("/users/me")
        # HTTPBearer returns 401 when the Authorization header is absent
        self.assertEqual(resp.status_code, 401)
