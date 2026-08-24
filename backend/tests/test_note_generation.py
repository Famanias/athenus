import asyncio
import json
import uuid
import pytest

from app.domain.learning.entities import Note, NoteSection
from app.domain.learning.note_generation import (
    ExtractedNotes,
    ExtractedNoteSection,
    build_notes_prompt,
    generate_notes_heuristic,
    parse_llm_notes,
)
from app.domain.learning.note_service import NoteService
from app.infrastructure.repositories.sqlite_note_repository import SqliteNoteRepository
from app.infrastructure.db.session import engine, init_db


def test_build_notes_prompt():
    chunks = [
        {"id": "c1", "start_time": 0.0, "end_time": 15.5, "text": "Welcome to neural networks."},
        {"id": "c2", "start_time": 15.5, "end_time": 45.0, "text": "Backpropagation computes gradients."},
    ]
    concepts = [
        {"name": "Neural Networks", "description": "Layered computing models.", "source_chunk_ids": ["c1"]},
    ]
    prompt = build_notes_prompt(chunks, concepts)
    assert "Neural Networks" in prompt
    assert "[chunk:c1]" in prompt
    assert "0.0s - 15.5s" in prompt
    assert "sections" in prompt
    assert "action_items" in prompt


def test_parse_llm_notes_valid_json():
    raw_json = json.dumps({
        "title": "Deep Learning Fundamentals",
        "summary": "An introduction to artificial neural networks and gradient descent.",
        "sections": [
            {
                "heading": "Introduction to Perceptrons",
                "body": "Perceptrons are linear binary classifiers.",
                "key_takeaways": ["Linear decision boundary", "Weights and bias"],
                "start_time": 0.0,
                "end_time": 30.0,
                "source_chunk_ids": ["chunk_0"]
            },
            {
                "heading": "Gradient Optimization",
                "body": "Loss functions guide parameter updates.",
                "key_takeaways": ["Learning rate tuning", "Convex vs non-convex loss"],
                "start_time": 30.0,
                "end_time": 90.0,
                "source_chunk_ids": ["chunk_1", "chunk_2"]
            }
        ],
        "action_items": [
            "Implement a single-layer perceptron in Python",
            "Derive the gradient of MSE loss"
        ]
    })

    parsed = parse_llm_notes(raw_json)
    assert parsed is not None
    assert parsed.title == "Deep Learning Fundamentals"
    assert len(parsed.sections) == 2
    assert parsed.sections[0].heading == "Introduction to Perceptrons"
    assert parsed.sections[0].start_time == 0.0
    assert parsed.sections[0].end_time == 30.0
    assert parsed.sections[0].source_chunk_ids == ["chunk_0"]
    assert len(parsed.sections[0].key_takeaways) == 2
    assert len(parsed.action_items) == 2


def test_parse_llm_notes_markdown_fences():
    raw_response = """Here are your structured study notes:
```json
{
  "title": "Clean Notes",
  "summary": "Synthesized overview.",
  "sections": [
    {
      "heading": "Core Principles",
      "body": "Explanation with markdown details.",
      "key_takeaways": ["Point A"],
      "start_time": 10.5,
      "end_time": 25.0,
      "source_chunk_ids": ["c1"]
    }
  ],
  "action_items": ["Review point A"]
}
```
Let me know if you need anything else!"""

    parsed = parse_llm_notes(raw_response)
    assert parsed is not None
    assert parsed.title == "Clean Notes"
    assert len(parsed.sections) == 1
    assert parsed.sections[0].heading == "Core Principles"
    assert parsed.sections[0].start_time == 10.5
    assert parsed.action_items == ["Review point A"]


def test_parse_llm_notes_malformed_returns_none():
    assert parse_llm_notes("") is None
    assert parse_llm_notes("Not JSON at all") is None
    assert parse_llm_notes("{\"invalid_key\": 123}") is None


def test_generate_notes_heuristic_empty():
    res = generate_notes_heuristic([])
    assert res.title == "Empty Notes"
    assert res.sections == []


def test_generate_notes_heuristic_with_chunks():
    chunks = [
        {"id": "chunk_1", "start_time": 0.0, "end_time": 20.0, "chunk_index": 0, "text": "First part discussing backpropagation algorithms in deep neural architectures."},
        {"id": "chunk_2", "start_time": 20.0, "end_time": 40.0, "chunk_index": 1, "text": "Second part explaining chain rule applications for gradient computation."},
        {"id": "chunk_3", "start_time": 40.0, "end_time": 60.0, "chunk_index": 2, "text": "Third part detailing learning rate scheduling and momentum optimizers."},
        {"id": "chunk_4", "start_time": 60.0, "end_time": 80.0, "chunk_index": 3, "text": "Final remarks on regularization techniques such as dropout and weight decay."},
    ]
    concepts = [
        {"name": "Backpropagation", "description": "Gradient calculation algorithm."},
        {"name": "Regularization", "description": "Prevents overfitting."},
    ]

    res = generate_notes_heuristic(chunks, concepts, version=1)
    assert res.title.startswith("Study Notes:")
    assert len(res.sections) >= 1
    assert res.sections[0].start_time == 0.0
    assert res.sections[-1].end_time == 80.0
    assert len(res.action_items) >= 1
    for sec in res.sections:
        assert sec.heading
        assert sec.body
        assert len(sec.key_takeaways) >= 1
        assert len(sec.source_chunk_ids) >= 1


def test_note_service_heuristic_execution():
    init_db()
    ws_id = f"ws_note_{uuid.uuid4().hex[:8]}"
    media_id = f"med_{uuid.uuid4().hex[:8]}"

    try:
        from sqlmodel import Session
    except ImportError:
        from sqlalchemy.orm import Session

    from app.infrastructure.db.models import MediaItemTable, TranscriptChunkTable


    with Session(engine) as session:
        media = MediaItemTable(
            id=media_id,
            workspace_id=ws_id,
            title="Calculus Lecture",
            file_path="/mock/path.mp4",
            status="completed",
        )
        session.add(media)

        for idx in range(3):
            session.add(
                TranscriptChunkTable(
                    id=f"chk_{media_id}_{idx}",
                    media_id=media_id,
                    workspace_id=ws_id,
                    text=f"Lecture chunk {idx} covering advanced calculus and linear algebra matrices.",
                    start_time=idx * 30.0,
                    end_time=(idx + 1) * 30.0,
                    chunk_index=idx,
                    word_count=10,
                )
            )
        session.commit()

    service = NoteService(
        ai_service_bus=None,
        repository=SqliteNoteRepository(),
    )  # None forces heuristic fallback

    note = asyncio.run(
        service.generate_notes(workspace_id=ws_id, media_id=media_id)
    )

    assert note is not None
    assert note.workspace_id == ws_id
    assert note.media_id == media_id
    assert note.version == 1
    assert note.status == "ready"
    assert note.generation_method == "heuristic"
    assert note.fallback_reason == "no_ai_bus"
    assert len(note.sections) >= 1
    assert len(note.action_items) >= 1


class FakeTextCapability:
    def __init__(self, response_text: str, provider_id: str = "mock-groq", default_model: str = "llama-3.3-70b"):
        self.response_text = response_text
        self.provider_id = provider_id
        self.default_model = default_model

    async def generate(self, request):
        class GenResult:
            def __init__(self, text):
                self.text = text
        return GenResult(self.response_text)


class FakeAIServiceBus:
    def __init__(self, capability):
        self._capability = capability

    def get_text_capability(self):
        return self._capability


def test_note_service_llm_execution():
    init_db()
    ws_id = f"ws_llm_{uuid.uuid4().hex[:8]}"
    media_id = f"med_llm_{uuid.uuid4().hex[:8]}"

    try:
        from sqlmodel import Session
    except ImportError:
        from sqlalchemy.orm import Session

    from app.infrastructure.db.models import MediaItemTable, TranscriptChunkTable

    with Session(engine) as session:
        session.add(
            MediaItemTable(
                id=media_id,
                workspace_id=ws_id,
                title="AI Lecture",
                file_path="/mock/ai.mp4",
                status="completed",
            )
        )
        session.add(
            TranscriptChunkTable(
                id=f"chk_{media_id}_0",
                media_id=media_id,
                workspace_id=ws_id,
                text="Transformers utilize self-attention mechanisms to process sequence data in parallel.",
                start_time=0.0,
                end_time=30.0,
                chunk_index=0,
                word_count=12,
            )
        )
        session.commit()

    llm_payload = json.dumps({
        "title": "Transformer Architectures",
        "summary": "Overview of self-attention mechanisms and parallel token processing.",
        "sections": [
            {
                "heading": "Self-Attention Mechanism",
                "body": "Computes attention weights between all token pairs dynamically.",
                "key_takeaways": ["Replaces sequential recurrence", "Scaled dot-product attention"],
                "start_time": 0.0,
                "end_time": 30.0,
                "source_chunk_ids": [f"chk_{media_id}_0"]
            }
        ],
        "action_items": ["Implement scaled dot-product attention in PyTorch"]
    })

    fake_bus = FakeAIServiceBus(FakeTextCapability(llm_payload))
    service = NoteService(ai_service_bus=fake_bus, repository=SqliteNoteRepository())

    note = asyncio.run(
        service.generate_notes(workspace_id=ws_id, media_id=media_id)
    )

    assert note is not None
    assert note.title == "Transformer Architectures"
    assert note.summary.startswith("Overview of self-attention")
    assert note.generation_method == "llm"
    assert note.fallback_reason is None
    assert len(note.sections) == 1
    assert note.sections[0].heading == "Self-Attention Mechanism"
    assert note.sections[0].start_time == 0.0
    assert note.sections[0].end_time == 30.0


def test_note_service_retry_on_429_success():
    from app.domain.ai.exceptions import LLMProviderRateLimitError

    init_db()
    ws_id = f"ws_retry_{uuid.uuid4().hex[:8]}"
    media_id = f"med_retry_{uuid.uuid4().hex[:8]}"

    try:
        from sqlmodel import Session
    except ImportError:
        from sqlalchemy.orm import Session

    from app.infrastructure.db.models import MediaItemTable, TranscriptChunkTable

    with Session(engine) as session:
        session.add(
            MediaItemTable(id=media_id, workspace_id=ws_id, title="Lecture", file_path="/mock/test.mp4", status="completed")
        )
        session.add(
            TranscriptChunkTable(id=f"chk_{media_id}_0", media_id=media_id, workspace_id=ws_id, text="Audio transcript text.", start_time=0.0, end_time=10.0, chunk_index=0, word_count=5)
        )
        session.commit()

    call_count = 0
    llm_payload = json.dumps({
        "title": "Recovered Notes",
        "summary": "Recovered summary.",
        "sections": [{"heading": "Section 1", "body": "Body text.", "key_takeaways": ["Point 1"]}],
        "action_items": ["Action 1"]
    })

    class FlakyCapability:
        provider_id = "groq"
        default_model = "llama-3.3-70b"

        async def generate(self, request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise LLMProviderRateLimitError("Rate limit exceeded", provider_id="groq", status_code=429, retry_after=0.01)
            class Result:
                text = llm_payload
            return Result()

    service = NoteService(
        ai_service_bus=FakeAIServiceBus(FlakyCapability()),
        repository=SqliteNoteRepository(),
    )
    note = asyncio.run(service.generate_notes(workspace_id=ws_id, media_id=media_id))

    assert note is not None
    assert call_count == 2
    assert note.generation_method == "llm"
    assert note.title == "Recovered Notes"


def test_note_service_fallback_on_persistent_429():
    from app.domain.ai.exceptions import LLMProviderRateLimitError

    init_db()
    ws_id = f"ws_fail_{uuid.uuid4().hex[:8]}"
    media_id = f"med_fail_{uuid.uuid4().hex[:8]}"

    try:
        from sqlmodel import Session
    except ImportError:
        from sqlalchemy.orm import Session

    from app.infrastructure.db.models import MediaItemTable, TranscriptChunkTable

    with Session(engine) as session:
        session.add(
            MediaItemTable(id=media_id, workspace_id=ws_id, title="Lecture", file_path="/mock/test.mp4", status="completed")
        )
        session.add(
            TranscriptChunkTable(id=f"chk_{media_id}_0", media_id=media_id, workspace_id=ws_id, text="Audio transcript text for testing persistent 429.", start_time=0.0, end_time=10.0, chunk_index=0, word_count=7)
        )
        session.commit()

    class FailingCapability:
        provider_id = "groq"
        default_model = "llama-3.3-70b"

        async def generate(self, request):
            raise LLMProviderRateLimitError("Rate limit persistent", provider_id="groq", status_code=429, retry_after=0.01)

    service = NoteService(
        ai_service_bus=FakeAIServiceBus(FailingCapability()),
        repository=SqliteNoteRepository(),
    )
    note = asyncio.run(service.generate_notes(workspace_id=ws_id, media_id=media_id))

    assert note is not None
    assert note.generation_method == "heuristic"
    assert note.fallback_reason == "rate_limit"


def test_note_service_fallback_on_parse_error():
    init_db()
    ws_id = f"ws_parse_fail_{uuid.uuid4().hex[:8]}"
    media_id = f"med_parse_fail_{uuid.uuid4().hex[:8]}"

    try:
        from sqlmodel import Session
    except ImportError:
        from sqlalchemy.orm import Session

    from app.infrastructure.db.models import MediaItemTable, TranscriptChunkTable

    with Session(engine) as session:
        session.add(
            MediaItemTable(id=media_id, workspace_id=ws_id, title="Lecture", file_path="/mock/test.mp4", status="completed")
        )
        session.add(
            TranscriptChunkTable(id=f"chk_{media_id}_0", media_id=media_id, workspace_id=ws_id, text="Audio transcript text.", start_time=0.0, end_time=10.0, chunk_index=0, word_count=5)
        )
        session.commit()

    class NonJsonCapability:
        provider_id = "groq"
        default_model = "llama-3.3-70b"

        async def generate(self, request):
            class Result:
                text = "This is plain prose without any JSON schema."
            return Result()

    service = NoteService(
        ai_service_bus=FakeAIServiceBus(NonJsonCapability()),
        repository=SqliteNoteRepository(),
    )
    note = asyncio.run(service.generate_notes(workspace_id=ws_id, media_id=media_id))

    assert note is not None
    assert note.generation_method == "heuristic"
    assert note.fallback_reason == "parse_error"


def test_note_service_caching_and_versioning():
    init_db()
    ws_id = f"ws_ver_{uuid.uuid4().hex[:8]}"
    media_id = f"med_ver_{uuid.uuid4().hex[:8]}"

    try:
        from sqlmodel import Session
    except ImportError:
        from sqlalchemy.orm import Session

    from app.infrastructure.db.models import MediaItemTable, TranscriptChunkTable

    with Session(engine) as session:
        session.add(
            MediaItemTable(
                id=media_id,
                workspace_id=ws_id,
                title="Physics Lecture",
                file_path="/mock/physics.mp4",
                status="completed",
            )
        )
        session.add(
            TranscriptChunkTable(
                id=f"chk_{media_id}_0",
                media_id=media_id,
                workspace_id=ws_id,
                text="Newton's laws of motion describe the relationship between a body and the forces acting upon it.",
                start_time=0.0,
                end_time=25.0,
                chunk_index=0,
                word_count=16,
            )
        )
        session.commit()

    service = NoteService(ai_service_bus=None, repository=SqliteNoteRepository())

    # 1. Initial generation (v1)
    note_v1 = asyncio.run(
        service.generate_notes(workspace_id=ws_id, media_id=media_id)
    )
    assert note_v1.version == 1

    # 2. Cached retrieval returns v1 without regeneration
    cached = asyncio.run(
        service.generate_notes(workspace_id=ws_id, media_id=media_id)
    )
    assert cached.id == note_v1.id
    assert cached.version == 1

    # 3. Forced regeneration yields immutable v2
    note_v2 = asyncio.run(
        service.generate_notes(workspace_id=ws_id, media_id=media_id, force_new_version=True)
    )
    assert note_v2.version == 2
    assert note_v2.id != note_v1.id

    # 4. List notes returns both versions
    notes_list = service.list_notes(ws_id, media_id=media_id)
    assert len(notes_list) == 2
    assert notes_list[0].version == 2
    assert notes_list[1].version == 1
