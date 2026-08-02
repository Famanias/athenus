from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

@dataclass
class EvaluationMetrics:
    retrieval_precision_at_5: float = 0.0
    retrieval_recall_at_5: float = 0.0
    citation_groundedness_score: float = 0.0
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0

@dataclass
class RetrievalBenchmark:
    id: str
    query: str
    expected_chunk_ids: list[str]
    retrieved_chunk_ids: list[str]
    metrics: EvaluationMetrics
    evaluated_at: datetime = field(default_factory=datetime.utcnow)
