from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, status

from src.application.auth.schemas import AuthSessionResponse, LoginRequest, RegisterUserRequest, UserProfileResponse
from src.core.config import Settings
from src.persistence.postgres.user_repository import PostgresUserRepository


class AuthService:
    def __init__(self, *, repository: PostgresUserRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def register(self, request: RegisterUserRequest) -> AuthSessionResponse:
        email = request.email.strip().lower()
        full_name = " ".join(request.full_name.strip().split())
        password = request.password.strip()

        if len(password) < self.settings.auth.password_min_length:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password must be at least {self.settings.auth.password_min_length} characters long.",
            )

        if self.repository.get_by_email(email) is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")

        now = datetime.now(timezone.utc)
        is_first_user = self.repository.count_users() == 0
        role = "admin" if is_first_user else "user"
        is_superuser = is_first_user

        user = self.repository.create_user(
            user_id=uuid4().hex,
            email=email,
            full_name=full_name,
            password_hash=self._hash_password(password),
            role=role,
            is_superuser=is_superuser,
            is_active=True,
            created_at=now,
            updated_at=now,
            last_login_at=now,
        )
        return self._build_session_response(user)

    def login(self, request: LoginRequest) -> AuthSessionResponse:
        email = request.email.strip().lower()
        password = request.password.strip()
        user = self.repository.get_by_email(email)
        if user is None or not user.is_active or not self._verify_password(password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

        updated = self.repository.update_last_login(email, datetime.now(timezone.utc)) or user
        return self._build_session_response(updated)

    def get_profile(self, email: str) -> UserProfileResponse:
        user = self.repository.get_by_email(email)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User session is no longer valid.")
        return self._to_profile(user)

    def decode_token(self, token: str) -> dict[str, object]:
        try:
            encoded_payload, encoded_signature = token.split(".", 1)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token.") from exc

        expected_signature = self._sign(encoded_payload.encode("utf-8"))
        try:
            provided_signature = self._b64decode(encoded_signature)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token.") from exc
        if not hmac.compare_digest(expected_signature, provided_signature):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token.")

        try:
            payload = json.loads(self._b64decode(encoded_payload).decode("utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token.") from exc

        exp = payload.get("exp")
        if not isinstance(exp, int) or exp < int(datetime.now(timezone.utc).timestamp()):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token has expired.")
        return payload

    def _build_session_response(self, user) -> AuthSessionResponse:
        profile = self._to_profile(user)
        return AuthSessionResponse(
            access_token=self._encode_token(
                {
                    "sub": user.email,
                    "role": user.role,
                    "superuser": user.is_superuser,
                }
            ),
            user=profile,
        )

    def _to_profile(self, user) -> UserProfileResponse:
        return UserProfileResponse(
            user_id=user.user_id,
            full_name=user.full_name,
            email=user.email,
            role=user.role,
            is_superuser=user.is_superuser,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )

    def _hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 310000)
        return f"pbkdf2_sha256${salt}${digest.hex()}"

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        try:
            algorithm, salt, digest = stored_hash.split("$", 2)
        except ValueError:
            return False
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 310000).hex()
        return hmac.compare_digest(candidate, digest)

    def _encode_token(self, payload: dict[str, object]) -> str:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=self.settings.auth.token_ttl_hours)
        resolved_payload = dict(payload)
        resolved_payload["exp"] = int(expires_at.timestamp())
        payload_blob = self._b64encode(json.dumps(resolved_payload, separators=(",", ":")).encode("utf-8"))
        signature = self._b64encode(self._sign(payload_blob.encode("utf-8")))
        return f"{payload_blob}.{signature}"

    def _sign(self, payload: bytes) -> bytes:
        secret = self._signing_secret().encode("utf-8")
        return hmac.new(secret, payload, hashlib.sha256).digest()

    def _signing_secret(self) -> str:
        explicit = self.settings.auth.session_signing_secret
        if explicit and explicit.strip():
            return explicit.strip()
        return self.settings.security.api_keys[0]

    @staticmethod
    def _b64encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")

    @staticmethod
    def _b64decode(value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(f"{value}{padding}".encode("utf-8"))
