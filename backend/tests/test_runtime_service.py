import os
import pytest
from app.core.runtime import RuntimeService, RuntimeEnvironment

def test_runtime_detection_default():
    service = RuntimeService()
    assert service.environment in (RuntimeEnvironment.NATIVE, RuntimeEnvironment.TAURI, RuntimeEnvironment.DOCKER)

def test_runtime_detection_docker_override(monkeypatch):
    monkeypatch.setenv("ATHENUS_RUNTIME", "docker")
    service = RuntimeService()
    assert service.environment == RuntimeEnvironment.DOCKER
    assert service.is_docker is True
    assert service.is_native is False
    assert service.can_access_host_filesystem is False

def test_runtime_detection_tauri_override(monkeypatch):
    monkeypatch.setenv("ATHENUS_RUNTIME", "tauri")
    service = RuntimeService()
    assert service.environment == RuntimeEnvironment.TAURI
    assert service.is_native is True
    assert service.can_access_host_filesystem is True

def test_runtime_detection_native_override(monkeypatch):
    monkeypatch.setenv("ATHENUS_RUNTIME", "native")
    service = RuntimeService()
    assert service.environment == RuntimeEnvironment.NATIVE
    assert service.is_docker is False
    assert service.is_native is True
    assert service.can_access_host_filesystem is True
