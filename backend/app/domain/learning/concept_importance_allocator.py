import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

@dataclass
class ConceptNodeDTO:
    id: str
    name: str
    weight: float = 1.0
    mastery_score: Optional[float] = None

@dataclass
class RelationDTO:
    source_concept: str
    target_concept: str

class ConceptImportanceAllocator:
    """Service ranking concepts by structural graph centrality & domain weight to compute budget allocations."""

    def calculate_allocations(
        self,
        concepts: List[ConceptNodeDTO],
        relations: List[RelationDTO],
        total_budget: int
    ) -> Dict[str, int]:
        """Compute item count allocations per concept respecting a target total budget limit."""
        if not concepts or total_budget <= 0:
            return {}

        # 1. Compute degree centrality for each concept
        degree_centrality: Dict[str, int] = {c.id: 0 for c in concepts}
        for rel in relations:
            if rel.source_concept in degree_centrality:
                degree_centrality[rel.source_concept] += 1
            if rel.target_concept in degree_centrality:
                degree_centrality[rel.target_concept] += 1

        # 2. Compute composite importance score per concept
        # Importance = weight * (1.0 + 0.5 * log2(1 + degree_centrality))
        # Weak concepts (mastery < 0.5) receive a 1.25x priority bonus
        scores: Dict[str, float] = {}
        for c in concepts:
            deg = degree_centrality.get(c.id, 0)
            base_importance = max(0.1, c.weight) * (1.0 + 0.5 * math.log2(1 + deg))
            
            # Apply low-mastery bonus if applicable
            if c.mastery_score is not None and c.mastery_score < 0.5:
                base_importance *= 1.25

            scores[c.id] = base_importance

        total_score = sum(scores.values())
        if total_score <= 0:
            avg_alloc = max(1, total_budget // len(concepts))
            return {c.id: avg_alloc for c in concepts}

        # 3. Proportional budget distribution
        allocations: Dict[str, int] = {}
        remaining_budget = total_budget

        # Sort concepts by importance score descending
        sorted_concepts = sorted(concepts, key=lambda c: scores[c.id], reverse=True)

        for c in sorted_concepts:
            if remaining_budget <= 0:
                allocations[c.id] = 0
                continue
            
            ratio = scores[c.id] / total_score
            allocated = max(1, round(total_budget * ratio))
            allocated = min(allocated, remaining_budget)
            
            allocations[c.id] = allocated
            remaining_budget -= allocated

        # Distribute any leftover budget to top concept
        if remaining_budget > 0 and sorted_concepts:
            allocations[sorted_concepts[0].id] += remaining_budget

        return allocations
