from __future__ import annotations

from pwdlib import PasswordHash


class PasswordService:
    def __init__(self) -> None:
        self.password_hash = PasswordHash.recommended()

    def hash_password(self, password: str) -> str:
        return self.password_hash.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            return self.password_hash.verify(password, password_hash)
        except Exception:
            return False
