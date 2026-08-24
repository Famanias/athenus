import ast
from pathlib import Path

from app.domain.workspace.workspace_service import WorkspaceService
from app.infrastructure.cache.memory_cache import MemoryCacheAdapter
import app.domain.workspace.workspace_service as workspace_module


DOMAIN_ROOT = Path(__file__).parents[1] / "app" / "domain"
CACHE_AWARE_DOMAIN_MODULES = (
    DOMAIN_ROOT / "knowledge" / "concept_merging.py",
    DOMAIN_ROOT / "knowledge" / "knowledge_graph_service.py",
    DOMAIN_ROOT / "settings" / "settings_service.py",
    DOMAIN_ROOT / "workspace" / "workspace_service.py",
)


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def test_cache_aware_domain_modules_depend_only_on_the_cache_port():
    violations = {
        str(path.relative_to(DOMAIN_ROOT)): [
            module
            for module in _imported_modules(path)
            if module.startswith("app.infrastructure.cache")
        ]
        for path in CACHE_AWARE_DOMAIN_MODULES
    }

    assert not any(violations.values()), violations


def test_workspace_deletion_invalidates_injected_cache_ports(monkeypatch):
    memory_cache = MemoryCacheAdapter()
    persistent_cache = MemoryCacheAdapter()
    monkeypatch.setattr(WorkspaceService, "_instance", None)
    monkeypatch.setattr(WorkspaceService, "_initialized", False)
    monkeypatch.setattr(workspace_module, "engine", None)

    service = WorkspaceService(
        application_cache=memory_cache,
        persistent_cache=persistent_cache,
    )
    service.create_workspace("Disposable", workspace_id="workspace-cache-qa")
    service.set_active_workspace_id("default")
    memory_cache.set("kg:ws:workspace-cache-qa:nodes", [1])
    memory_cache.set("rag:workspace-cache-qa:query", [2])
    persistent_cache.set("llm:ws:workspace-cache-qa:prompt", "answer")

    assert service.delete_workspace("workspace-cache-qa") is True
    assert memory_cache.get("kg:ws:workspace-cache-qa:nodes") is None
    assert memory_cache.get("rag:workspace-cache-qa:query") is None
    assert persistent_cache.get("llm:ws:workspace-cache-qa:prompt") is None
