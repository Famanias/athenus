import os
import sys
from enum import Enum

class RuntimeEnvironment(str, Enum):
    NATIVE = "native"
    DOCKER = "docker"
    TAURI = "tauri"
    WEB = "web"

class RuntimeService:
    """Centralized platform runtime environment detection service."""

    def __init__(self) -> None:
        self._environment = self._detect_environment()

    def _detect_environment(self) -> RuntimeEnvironment:
        env_override = os.getenv("ATHENUS_RUNTIME")
        if env_override:
            try:
                return RuntimeEnvironment(env_override.lower())
            except ValueError:
                pass

        # Check for Linux Docker container markers
        if os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER") == "true":
            return RuntimeEnvironment.DOCKER

        # Check for Tauri Desktop IPC markers
        if os.getenv("TAURI_ENV") == "true" or os.getenv("IPC_BEARER_TOKEN"):
            return RuntimeEnvironment.TAURI

        return RuntimeEnvironment.NATIVE

    @property
    def environment(self) -> RuntimeEnvironment:
        return self._environment

    @property
    def is_docker(self) -> bool:
        return self._environment == RuntimeEnvironment.DOCKER

    @property
    def is_native(self) -> bool:
        return self._environment in (RuntimeEnvironment.NATIVE, RuntimeEnvironment.TAURI)

    @property
    def can_access_host_filesystem(self) -> bool:
        return self.is_native

runtime_service = RuntimeService()
