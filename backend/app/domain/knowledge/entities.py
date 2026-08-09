from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

class RelationType(str, Enum):
    PREREQUISITE_FOR = "prerequisite_for"
    RELATED_TO = "related_to"
    EXPANDS_ON = "expands_on"
    CONTRADICTS = "contradicts"
    EXAMPLE_OF = "example_of"

@dataclass
class TimestampWindow:
    start_time: float
    end_time: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end_time - self.start_time)

@dataclass
class SourceContentUnit:
    id: str
    source_id: str
    workspace_id: str
    text: str
    location: Dict[str, Any] = field(default_factory=dict)
    chunk_index: int = 0
    word_count: int = 0
    embedding: Optional[List[float]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class TranscriptChunk:
    id: str
    media_id: str
    workspace_id: str
    text: str
    start_time: float
    end_time: float
    chunk_index: int
    word_count: int = 0
    location: Optional[Dict[str, Any]] = None
    embedding: Optional[List[float]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConceptNode:
    id: str
    workspace_id: str
    name: str
    description: str
    source_chunk_ids: List[str] = field(default_factory=list)
    mastery_level: float = 0.0
    # Grounding & provenance contract
    status: str = "ready"
    media_id: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None

@dataclass
class ConceptRelation:
    id: str
    source_concept_id: str
    target_concept_id: str
    relation_type: RelationType
    weight: float = 1.0
    media_id: Optional[str] = None

class KnowledgeGraphProtocol(Protocol):
    def add_node(self, node: ConceptNode) -> None: ...
    def add_edge(self, source_id: str, target_id: str, relation: RelationType, weight: float = 1.0) -> None: ...
    def find_related(self, concept_id: str, max_depth: int = 2) -> List[ConceptNode]: ...
    def recommend_prerequisites(self, target_concept_id: str) -> List[ConceptNode]: ...
