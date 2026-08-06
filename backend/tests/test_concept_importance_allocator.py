import pytest
from app.domain.learning.concept_importance_allocator import (
    ConceptImportanceAllocator,
    ConceptNodeDTO,
    RelationDTO,
)

def test_concept_importance_allocation():
    allocator = ConceptImportanceAllocator()

    # Define 3 concepts with different weights & graph connections
    concepts = [
        ConceptNodeDTO(id="c1", name="React", weight=2.0),
        ConceptNodeDTO(id="c2", name="Virtual DOM", weight=1.0),
        ConceptNodeDTO(id="c3", name="JSX Syntax", weight=0.5),
    ]

    # React connects to Virtual DOM and JSX Syntax
    relations = [
        RelationDTO(source_concept="c1", target_concept="c2"),
        RelationDTO(source_concept="c1", target_concept="c3"),
    ]

    # Target total budget = 10 items
    allocations = allocator.calculate_allocations(concepts, relations, total_budget=10)

    assert sum(allocations.values()) == 10
    # React (c1) has highest weight and degree centrality -> gets highest allocation
    assert allocations["c1"] > allocations["c2"]
    assert allocations["c2"] >= allocations["c3"]
    assert allocations["c3"] >= 1

def test_low_mastery_bonus():
    allocator = ConceptImportanceAllocator()

    concepts = [
        ConceptNodeDTO(id="c1", name="Mastered Topic", weight=1.0, mastery_score=0.9),
        ConceptNodeDTO(id="c2", name="Weak Topic", weight=1.0, mastery_score=0.2),
    ]
    relations = []

    allocations = allocator.calculate_allocations(concepts, relations, total_budget=10)

    assert sum(allocations.values()) == 10
    assert allocations["c2"] > allocations["c1"]
