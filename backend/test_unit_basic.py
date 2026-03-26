"""
Unit tests for auth.py helper functions.

These tests cover pure functions with no database or network dependencies.

Run from the backend/ directory:
    pytest test_unit_basic.py -v
"""
import sys
import os

# Ensure imports resolve from backend/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
from fastapi import HTTPException
from routers.auth import hash_password, verify_password, create_access_token, decode_token


class TestPasswordHashing:
    """Tests for hash_password() and verify_password()."""

    def test_hash_is_not_plaintext(self):
        hashed = hash_password("SecurePass123!")
        assert hashed != "SecurePass123!"
        assert hashed.startswith("$2b$")  # bcrypt output format

    def test_correct_password_verifies(self):
        hashed = hash_password("SecurePass123!")
        assert verify_password("SecurePass123!", hashed) is True

    def test_wrong_password_does_not_verify(self):
        hashed = hash_password("SecurePass123!")
        assert verify_password("WrongPassword!", hashed) is False


class TestJWTTokens:
    """Tests for create_access_token() and decode_token()."""

    def test_token_roundtrip_preserves_payload(self):
        data = {"user_id": 7, "email": "doc@hospital.rw", "role": "doctor"}
        token = create_access_token(data)
        payload = decode_token(token)
        assert payload["user_id"] == 7
        assert payload["email"] == "doc@hospital.rw"
        assert payload["role"] == "doctor"

    def test_invalid_token_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            decode_token("not.a.real.token")
        assert exc_info.value.status_code == 401
