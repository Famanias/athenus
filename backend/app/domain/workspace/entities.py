from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

@dataclass
class Workspace:
    id: str
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    media_item_ids: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
