import os
import pytest
from app.core.runtime import RuntimeService, RuntimeEnvironment
from app.services.filesystem_service import (
    FilesystemService,
    DirectoryNotFoundError,
    HostPathInaccessibleError,
)

def test_filesystem_service_empty_path():
    service = FilesystemService()
    with pytest.raises(DirectoryNotFoundError, match="Directory path cannot be empty"):
        service.validate_and_normalize_path("   ")

def test_filesystem_service_nonexistent_path(tmp_path):
    service = FilesystemService()
    non_existent = str(tmp_path / "non_existent_subfolder")
    with pytest.raises(DirectoryNotFoundError, match="does not exist on disk"):
        service.validate_and_normalize_path(non_existent)

def test_filesystem_service_valid_path(tmp_path):
    service = FilesystemService()
    valid_dir = str(tmp_path)
    normalized = service.validate_and_normalize_path(valid_dir)
    assert os.path.exists(normalized)

def test_filesystem_service_docker_unmounted_windows_drive(monkeypatch):
    monkeypatch.setenv("ATHENUS_RUNTIME", "docker")
    docker_runtime = RuntimeService()
    service = FilesystemService(runtime=docker_runtime)

    raw_win_path = r"E:\ollama\models"
    with pytest.raises(HostPathInaccessibleError) as exc_info:
        service.validate_and_normalize_path(raw_win_path)

    err_msg = str(exc_info.value)
    assert "You are currently using docker" in err_msg
    assert "switch to Native / Non-Docker Mode (Manual Virtual Environment)" in err_msg
    assert "ONBOARDING.md" in err_msg
    assert "\n If you are using docker, ignore this error." in err_msg
    # Ensure raw path mangling like /app/E:\... is NOT present in the error
    assert "/app/" not in err_msg
