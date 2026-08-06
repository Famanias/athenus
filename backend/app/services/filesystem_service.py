import os
import re
import sys
from typing import Optional
from app.core.runtime import RuntimeService, runtime_service

class DirectoryNotFoundError(Exception):
    """Raised when the specified directory path does not exist on disk."""
    pass

class HostPathInaccessibleError(DirectoryNotFoundError):
    """Raised when a host directory path is inaccessible due to container isolation boundaries."""
    pass

class FilesystemService:
    """Decoupled filesystem path validation and normalization service."""

    def __init__(self, runtime: Optional[RuntimeService] = None) -> None:
        self.runtime = runtime or runtime_service

    def validate_and_normalize_path(self, raw_path: str) -> str:
        """
        Normalizes and validates filesystem paths while respecting platform container boundaries.
        Returns normalized absolute path string.
        """
        if not raw_path or not raw_path.strip():
            raise DirectoryNotFoundError("Directory path cannot be empty.")

        clean_path = raw_path.strip()

        # Detect Windows drive letter syntax (e.g. E:\ or C:/) when running inside Docker
        is_windows_drive = bool(re.match(r"^[a-zA-Z]:[\\/]", clean_path))

        if self.runtime.is_docker and is_windows_drive:
            raise HostPathInaccessibleError(
                "You are currently using docker, if you want to manually add the path of your ollama models, "
                "switch to Native / Non-Docker Mode (Manual Virtual Environment). "
                "For more information, check the docs\\ONBOARDING.md"
                "\n If you are using docker, ignore this error."
            )

        clean_path = os.path.abspath(clean_path)

        if not os.path.exists(clean_path) or not os.path.isdir(clean_path):
            raise DirectoryNotFoundError(f"Directory '{clean_path}' does not exist on disk.")

        return clean_path

filesystem_service = FilesystemService()
