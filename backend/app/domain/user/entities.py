from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

@dataclass
class ConceptMastery:
    concept_id: str
    mastery_score: float = 0.0  # 0.0 to 1.0
    review_count: int = 0
    last_reviewed_at: Optional[datetime] = None
    next_review_due_at: Optional[datetime] = None

@dataclass
class UserMemory:
    user_id: str
    workspace_id: str
    concept_mastery_map: Dict[str, ConceptMastery] = field(default_factory=dict)
    preferred_learning_style: str = "visual"
    notes: List[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.utcnow)
