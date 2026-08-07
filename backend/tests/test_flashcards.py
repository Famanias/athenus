import asyncio
import io
import os
import uuid

from app.domain.learning.entities import FlashcardCard
from app.domain.learning.flashcard_service import FlashcardService
from app.domain.learning.sm2 import sm2_review
from app.domain.knowledge.entities import ConceptNode
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService
from app.infrastructure.exporters.anki_exporter import (
    export_deck_apkg,
    export_deck_csv,
)
from app.infrastructure.db.session import engine, init_db

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


def _seed_graph(workspace_id: str = "ws_flash") -> None:
    service = KnowledgeGraphService()
    uid = uuid.uuid4().hex[:8]
    c1_id = f"{workspace_id}_c1_{uid}"
    c2_id = f"{workspace_id}_c2_{uid}"
    c1 = ConceptNode(id=c1_id, workspace_id=workspace_id, name="Gradient Descent", description="Iterative optimization algorithm minimizing a loss function.")
    c2 = ConceptNode(id=c2_id, workspace_id=workspace_id, name="Learning Rate", description="Step size controlling parameter updates.")
    service.add_concept(c1)
    service.add_concept(c2)
    service.add_relation(c1_id, c2_id, None, workspace_id=workspace_id)


# ---------------------------------------------------------------------------
# SM-2 algorithm
# ---------------------------------------------------------------------------
def test_sm2_first_success():
    result = sm2_review(rating=3)
    assert result.ease_factor == 2.5
    assert result.interval_days == 1
    assert result.repetitions == 1


def test_sm2_second_success():
    result = sm2_review(ease_factor=2.5, interval_days=1, repetitions=1, rating=3)
    assert result.interval_days == 6
    assert result.repetitions == 2


def test_sm2_interval_growth():
    result = sm2_review(ease_factor=2.5, interval_days=6, repetitions=2, rating=3)
    assert result.interval_days == round(6 * 2.5)
    assert result.repetitions == 3


def test_sm2_easy_increases_ef():
    result = sm2_review(rating=4)
    assert result.ease_factor > 2.5


def test_sm2_hard_decreases_ef():
    result = sm2_review(rating=2)
    assert result.ease_factor < 2.5


def test_sm2_fail_resets():
    result = sm2_review(ease_factor=2.5, interval_days=60, repetitions=5, rating=1)
    assert result.interval_days == 1
    assert result.repetitions == 0
    assert result.ease_factor < 2.5


# ---------------------------------------------------------------------------
# Flashcard service (on-demand versioned decks, SM-2 reviews)
# ---------------------------------------------------------------------------
def test_generate_deck_heuristic_fallback():
    init_db()
    ws = f"ws_flash_{uuid.uuid4().hex[:8]}"
    _seed_graph(ws)
    service = FlashcardService()
    deck = asyncio.run(
        service.generate_deck(workspace_id=ws)
    )
    assert deck.status == "ready"
    assert deck.version == 1
    assert deck.card_count >= 1
    cards = service.get_deck_cards(deck.id)
    assert len(cards) >= 1
    assert cards[0].card_type in {"basic", "cloze", "definition", "true_false"}
    assert cards[0].workspace_id == ws


def test_deck_caching_and_versioning():
    init_db()
    ws = f"ws_version_{uuid.uuid4().hex[:8]}"
    _seed_graph(ws)
    service = FlashcardService()
    deck_v1 = asyncio.run(
        service.generate_deck(workspace_id=ws)
    )
    # Cached: same deck returned, no new version.
    cached = asyncio.run(
        service.generate_deck(workspace_id=ws)
    )
    assert cached.id == deck_v1.id
    assert cached.version == 1
    # Forced: immutable v2 created.
    deck_v2 = asyncio.run(
        service.generate_deck(workspace_id=ws, force_new_version=True)
    )
    assert deck_v2.version == 2
    assert deck_v2.id != deck_v1.id
    decks = service.list_decks(ws)
    assert len(decks) == 2


def test_record_review_uses_sm2():
    init_db()
    ws = f"ws_review_{uuid.uuid4().hex[:8]}"
    _seed_graph(ws)
    service = FlashcardService()
    deck = asyncio.run(
        service.generate_deck(workspace_id=ws)
    )
    cards = service.get_deck_cards(deck.id)
    assert cards
    card = cards[0]
    review1 = service.record_review(card.id, ws, rating=3)
    assert review1.ease_factor == 2.5
    assert review1.repetitions == 1
    assert review1.interval_days == 1
    review2 = service.record_review(card.id, ws, rating=4)
    assert review2.repetitions == 2
    assert review2.interval_days == 6
    assert review2.ease_factor > 2.5
    # Failure resets scheduling.
    review3 = service.record_review(card.id, ws, rating=1)
    assert review3.repetitions == 0
    assert review3.interval_days == 1


def test_due_cards_initial():
    init_db()
    ws = f"ws_due_{uuid.uuid4().hex[:8]}"
    _seed_graph(ws)
    service = FlashcardService()
    deck = asyncio.run(
        service.generate_deck(workspace_id=ws)
    )
    due = service.due_cards(ws)
    assert len(due) == deck.card_count


# ---------------------------------------------------------------------------
# Anki exporter
# ---------------------------------------------------------------------------
def _sample_cards() -> list:
    return [
        FlashcardCard(
            id="card_a",
            deck_id="deck_x",
            workspace_id="ws",
            card_type="basic",
            front="What is Gradient Descent?",
            back="An iterative optimization algorithm.",
            concept_name="Gradient Descent",
            media_id="m1",
            start_time=12.5,
        ),
        FlashcardCard(
            id="card_b",
            deck_id="deck_x",
            workspace_id="ws",
            card_type="cloze",
            front="",
            cloze_text="The {{c1::learning rate}} controls step size.",
            back="Hyperparameter tuning note.",
            concept_name="Learning Rate",
        ),
    ]


def test_csv_export_contains_cards():
    content = export_deck_csv(_sample_cards())
    assert "Gradient Descent" in content
    assert "learning rate" in content


def test_apkg_export_valid_zip_with_anki2():
    buffer = io.BytesIO()
    export_deck_apkg(_sample_cards(), buffer)
    buffer.seek(0)
    import tempfile
    import zipfile
    with zipfile.ZipFile(buffer) as zf:
        names = zf.namelist()
        assert "collection.anki2" in names
        assert "media" in names
        data = zf.read("collection.anki2")
        import sqlite3
        db_path = os.path.join(tempfile.gettempdir(), f"test_{uuid.uuid4().hex}.anki2")
        with open(db_path, "wb") as f:
            f.write(data)
        conn = sqlite3.connect(db_path)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"col", "notes", "cards", "revlog"} <= tables
        n_notes = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        assert n_notes == 2
        conn.close()
        os.remove(db_path)


def test_consecutive_regeneration_produces_distinct_content():
    init_db()
    ws_id = f"ws_regen_{uuid.uuid4().hex[:8]}"
    _seed_graph(ws_id)
    service = FlashcardService()

    deck1 = asyncio.run(service.generate_deck(ws_id, force_new_version=False))
    cards1 = service.get_deck_cards(deck1.id)

    deck2 = asyncio.run(service.generate_deck(ws_id, force_new_version=True))
    cards2 = service.get_deck_cards(deck2.id)

    assert deck1.version == 1
    assert deck2.version == 2
    assert deck1.id != deck2.id
    # Assert card fronts/clozes vary between v1 and v2
    fronts1 = [c.front or c.cloze_text for c in cards1]
    fronts2 = [c.front or c.cloze_text for c in cards2]
    assert fronts1 != fronts2

