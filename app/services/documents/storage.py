from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.core.config import Settings


class LocalDocumentStorageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build_storage_path(self, *, user_id: UUID, document_id: UUID, extension: str) -> Path:
        storage_path = self.settings.resolved_uploads_dir / str(user_id) / f"{document_id}.{extension}"
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        return storage_path

    def save(self, *, path: Path, content: bytes) -> None:
        path.write_bytes(content)

    def resolve(self, stored_path: str) -> Path:
        path = Path(stored_path)
        if path.is_absolute():
            return path
        return (self.settings.resolved_uploads_dir.parent / path).resolve()

    def delete(self, stored_path: str) -> None:
        resolved = self.resolve(stored_path)
        resolved.unlink(missing_ok=True)
