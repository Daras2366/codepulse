"""Authentication endpoint tests.

Covers:
    - POST /auth/register — success and duplicate email
    - POST /auth/login    — success, wrong password, unknown email
    - GET  /users/me      — with valid token, without token
    - Logout (client-side only; clearing token prevents /users/me from working)
    - Argon2 password hashing
    - Legacy bcrypt password compatibility
    - Unicode password handling
    - JWT validation
    - Inactive user handling
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
from app.core.security import hash_password, verify_password, needs_rehash
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

    def test_register_hashes_password_with_argon2(self):
        """New passwords must be hashed with Argon2."""
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
        # Argon2 hashes start with $argon2
        self.assertTrue(user.password_hash.startswith("$argon2"))

    def test_register_duplicate_email_returns_400(self):
        payload = {
            "username": "carol",
            "email": "carol@example.com",
            "password": "password123",
        }
        self.client.post("/auth/register", json=payload)
        # Second registration with same email
        resp = self.client.post(
            "/auth/register",
            json={**payload, "username": "carol2"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_register_password_too_short_returns_422(self):
        resp = self.client.post(
            "/auth/register",
            json={
                "username": "dave",
                "email": "dave@example.com",
                "password": "short",
            },
        )
        self.assertEqual(resp.status_code, 422)

    def test_register_password_too_long_returns_422(self):
        resp = self.client.post(
            "/auth/register",
            json={
                "username": "eve",
                "email": "eve@example.com",
                "password": "a" * 129,
            },
        )
        self.assertEqual(resp.status_code, 422)


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

        # Seed a user with Argon2 hash
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


class LegacyBcryptTests(TestCase):
    """Legacy bcrypt password compatibility and upgrade"""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

        # Seed a user with bcrypt hash (legacy) - use bcrypt directly
        import bcrypt
        bcrypt_hash = bcrypt.hashpw(b"legacy123", bcrypt.gensalt()).decode("utf-8")

        self.user = User(
            username="legacy",
            email="legacy@example.com",
            password_hash=bcrypt_hash,
        )
        self.session.add(self.user)
        self.session.commit()

        self.client = TestClient(_build_app(self.session))

    def tearDown(self):
        self.client.close()
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_legacy_bcrypt_login_succeeds(self):
        """Legacy bcrypt passwords should still work."""
        resp = self.client.post(
            "/auth/login",
            json={"email": "legacy@example.com", "password": "legacy123"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("access_token", data)

    def test_legacy_bcrypt_upgrades_to_argon2(self):
        """Successful login with bcrypt should upgrade to Argon2."""
        # Verify initial hash is bcrypt
        user = self.session.query(User).filter_by(email="legacy@example.com").first()
        self.assertTrue(user.password_hash.startswith("$2"))

        # Login
        self.client.post(
            "/auth/login",
            json={"email": "legacy@example.com", "password": "legacy123"},
        )

        # Verify hash was upgraded to Argon2
        self.session.refresh(user)
        self.assertTrue(user.password_hash.startswith("$argon2"))

    def test_legacy_bcrypt_long_password_compatible(self):
        """Bcrypt 72-byte limit should be handled compatibly."""
        # Create a password that exceeds 72 bytes in UTF-8
        # Each '€' is 3 bytes in UTF-8, so 25 of them = 75 bytes
        long_password = "€" * 25

        import bcrypt
        bcrypt_hash = bcrypt.hashpw(long_password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")

        user = User(
            username="longpass",
            email="longpass@example.com",
            password_hash=bcrypt_hash,
        )
        self.session.add(user)
        self.session.commit()

        # Should still login successfully with the same password
        resp = self.client.post(
            "/auth/login",
            json={"email": "longpass@example.com", "password": long_password},
        )
        self.assertEqual(resp.status_code, 200)


class UnicodePasswordTests(TestCase):
    """Unicode password handling"""

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

    def test_unicode_password_login_succeeds(self):
        """Unicode passwords should work correctly."""
        unicode_password = "パスワード123"

        # Register with unicode password
        self.client.post(
            "/auth/register",
            json={
                "username": "unicode",
                "email": "unicode@example.com",
                "password": unicode_password,
            },
        )

        # Login with same unicode password
        resp = self.client.post(
            "/auth/login",
            json={"email": "unicode@example.com", "password": unicode_password},
        )
        self.assertEqual(resp.status_code, 200)


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


class InactiveUserTests(TestCase):
    """Inactive user authentication handling"""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

        # Create an inactive user
        self.user = User(
            username="inactive",
            email="inactive@example.com",
            password_hash=hash_password("password123"),
            is_active=False,
        )
        self.session.add(self.user)
        self.session.commit()

        self.client = TestClient(_build_app(self.session))

    def tearDown(self):
        self.client.close()
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_inactive_user_cannot_login(self):
        """Inactive users should not be able to authenticate."""
        # First, verify password verification works
        self.assertTrue(verify_password("password123", self.user.password_hash))

        # Try to login - should fail because user is inactive
        resp = self.client.post(
            "/auth/login",
            json={"email": "inactive@example.com", "password": "password123"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_inactive_user_token_rejected(self):
        """Even with a valid token, inactive users should be rejected."""
        # Get a token for the inactive user by creating it directly
        from app.core.security import create_access_token
        token = create_access_token({"sub": "inactive@example.com"})

        # Try to access /users/me with the token
        resp = self.client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(resp.status_code, 401)


class SecurityHelperTests(TestCase):
    """Security helper function tests"""

    def test_verify_password_argon2(self):
        """Argon2 password verification should work."""
        password = "testpassword123"
        hashed = hash_password(password)
        self.assertTrue(hashed.startswith("$argon2"))
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("wrongpassword", hashed))

    def test_verify_password_bcrypt(self):
        """Bcrypt password verification should work."""
        import bcrypt
        password = "testpassword123"
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        self.assertTrue(hashed.startswith("$2"))
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("wrongpassword", hashed))

    def test_needs_rehash_bcrypt(self):
        """Bcrypt hashes should need rehashing."""
        import bcrypt
        hashed = bcrypt.hashpw(b"password", bcrypt.gensalt()).decode("utf-8")
        self.assertTrue(needs_rehash(hashed))

    def test_needs_rehash_argon2(self):
        """Argon2 hashes should not need rehashing."""
        hashed = hash_password("password")
        self.assertFalse(needs_rehash(hashed))
