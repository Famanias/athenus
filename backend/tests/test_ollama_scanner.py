import os
import tempfile
import pytest
from app.services.ollama_scanner import (
    OllamaModelScanner,
    DirectoryNotFoundError,
    InvalidOllamaDirectoryError,
)

def test_scan_non_existent_directory():
    scanner = OllamaModelScanner()
    with pytest.raises(DirectoryNotFoundError):
        scanner.scan("C:\\NonExistentPath_Athenus_Test_123")

def test_scan_invalid_directory():
    scanner = OllamaModelScanner()
    with tempfile.TemporaryDirectory() as tmp_dir:
        with pytest.raises(InvalidOllamaDirectoryError):
            scanner.scan(tmp_dir)

def test_scan_valid_ollama_structure():
    scanner = OllamaModelScanner()
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Build mock Ollama structure: <tmp>/manifests/registry.ollama.ai/library/llama3/8b
        manifest_dir = os.path.join(tmp_dir, "manifests", "registry.ollama.ai", "library", "llama3")
        os.makedirs(manifest_dir, exist_ok=True)
        manifest_file = os.path.join(manifest_dir, "8b")
        with open(manifest_file, "w") as f:
            f.write('{"schemaVersion": 2}')

        config_dir, resolved_dir, models = scanner.scan(tmp_dir)
        assert config_dir == os.path.abspath(tmp_dir)
        assert resolved_dir == os.path.abspath(tmp_dir)
        assert len(models) == 1
        assert models[0].full_id == "llama3:8b"
        assert models[0].model_name == "llama3"
        assert models[0].tag == "8b"
        assert models[0].provider == "ollama"

def test_scan_parent_ollama_folder_normalization():
    scanner = OllamaModelScanner()
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Parent .ollama containing models subfolder
        ollama_parent = os.path.join(tmp_dir, ".ollama")
        models_sub = os.path.join(ollama_parent, "models")
        manifest_dir = os.path.join(models_sub, "manifests", "registry.ollama.ai", "library", "mistral")
        os.makedirs(manifest_dir, exist_ok=True)
        with open(os.path.join(manifest_dir, "latest"), "w") as f:
            f.write('{"schemaVersion": 2}')

        config_dir, resolved_dir, models = scanner.scan(ollama_parent)
        assert config_dir == os.path.abspath(ollama_parent)
        assert resolved_dir == os.path.abspath(models_sub)
        assert len(models) == 1
        assert models[0].full_id == "mistral:latest"
