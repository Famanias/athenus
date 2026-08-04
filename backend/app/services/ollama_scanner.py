from dataclasses import dataclass
import os
from typing import List, Optional
from app.services.filesystem_service import (
    DirectoryNotFoundError,
    HostPathInaccessibleError,
    FilesystemService,
    filesystem_service as default_fs_service,
)

class InvalidOllamaDirectoryError(Exception):
    """Raised when the directory structure does not match a valid Ollama models directory."""
    pass

@dataclass
class DiscoveredModel:
    full_id: str
    model_name: str
    tag: str
    provider: str = "ollama"
    size_bytes: Optional[int] = None

class OllamaModelScanner:
    """100% Filesystem-based scanner for local Ollama model directories."""

    def __init__(self, fs_service: Optional[FilesystemService] = None) -> None:
        self.fs_service = fs_service or default_fs_service

    def normalize_and_validate_path(self, raw_path: str) -> tuple[str, str]:
        """
        Normalizes candidate paths (.ollama, .ollama/models, .ollama/models/manifests)
        and validates existence and structural integrity.
        Returns tuple: (configured_dir, resolved_dir)
        """
        clean_path = self.fs_service.validate_and_normalize_path(raw_path)

        # Forgiving path normalization: check candidate target subfolders
        resolved_path = clean_path

        # If user selected .ollama parent, check for models subfolder
        if os.path.basename(clean_path).lower() == ".ollama":
            models_subfolder = os.path.join(clean_path, "models")
            if os.path.exists(models_subfolder) and os.path.isdir(models_subfolder):
                resolved_path = models_subfolder

        # If user selected manifests subfolder, navigate up to models folder
        if os.path.basename(clean_path).lower() == "manifests":
            parent = os.path.dirname(clean_path)
            if os.path.basename(parent).lower() == "models":
                resolved_path = parent

        # Structural validation: verify presence of manifests or blobs directory
        manifests_dir = os.path.join(resolved_path, "manifests")
        blobs_dir = os.path.join(resolved_path, "blobs")

        if not (os.path.exists(manifests_dir) or os.path.exists(blobs_dir) or os.path.basename(resolved_path).lower() == "manifests"):
            raise InvalidOllamaDirectoryError(
                f"Directory '{clean_path}' is not a valid Ollama models directory (missing 'manifests' or 'blobs' subfolders)."
            )

        return clean_path, resolved_path

    def scan(self, raw_path: str) -> tuple[str, str, List[DiscoveredModel]]:
        """
        Scans the specified path for installed Ollama models.
        Returns: (configured_dir, resolved_dir, discovered_models)
        """
        configured_dir, resolved_dir = self.normalize_and_validate_path(raw_path)

        manifests_root = os.path.join(resolved_dir, "manifests")
        if not os.path.exists(manifests_root) and os.path.basename(resolved_dir).lower() == "manifests":
            manifests_root = resolved_dir

        discovered: List[DiscoveredModel] = []
        seen_ids = set()

        if os.path.exists(manifests_root):
            # Traverse manifests/ registry hierarchy e.g. manifests/registry.ollama.ai/library/<model>/<tag>
            for root, _, files in os.walk(manifests_root):
                for filename in files:
                    # Ignore non-manifest files or system files
                    if filename.startswith(".") or filename.endswith(".json") or filename == "sha256":
                        continue

                    rel_path = os.path.relpath(root, manifests_root)
                    parts = [p for p in rel_path.replace("\\", "/").split("/") if p and p not in [".", ".."]]

                    # Standard path layout: [registry, "library", model_name] or [model_name]
                    if len(parts) >= 1:
                        model_name = parts[-1]
                        tag = filename

                        # Skip registry domain names in model_name if any
                        if "." in model_name and len(parts) > 1:
                            model_name = parts[-1]

                        full_id = f"{model_name}:{tag}"
                        if full_id not in seen_ids:
                            seen_ids.add(full_id)

                            manifest_file = os.path.join(root, filename)
                            file_size = None
                            try:
                                file_size = os.path.getsize(manifest_file)
                            except Exception:
                                pass

                            discovered.append(
                                DiscoveredModel(
                                    full_id=full_id,
                                    model_name=model_name,
                                    tag=tag,
                                    provider="ollama",
                                    size_bytes=file_size
                                )
                            )

        # Sort discovered models alphabetically by full_id
        discovered.sort(key=lambda m: m.full_id)
        return configured_dir, resolved_dir, discovered
