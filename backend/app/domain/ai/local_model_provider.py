from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel

class ProviderStatusDTO(BaseModel):
    provider_id: str
    label: str
    connected: bool = False
    version: Optional[str] = None
    base_url: Optional[str] = None
    error: Optional[str] = None

class CatalogModelDTO(BaseModel):
    full_id: str
    name: str
    tag: str
    provider_id: str = "ollama"
    size_bytes: Optional[int] = None

class ModelCatalogDTO(BaseModel):
    provider_id: str
    models: List[CatalogModelDTO] = []
    count: int = 0

class ILocalModelProvider(ABC):
    """Domain interface for local AI model providers that enumerate installed models."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        pass

    @property
    @abstractmethod
    def label(self) -> str:
        pass

    @abstractmethod
    async def get_status(self) -> ProviderStatusDTO:
        pass

    @abstractmethod
    async def list_models(self) -> ModelCatalogDTO:
        pass
