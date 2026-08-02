from app.domain.media.entities import MediaItem, ProcessingStatus, MediaType
from app.domain.workspace.entities import Workspace
from app.domain.knowledge.entities import TranscriptChunk, TimestampWindow, ConceptNode, RelationType
from app.domain.user.entities import UserMemory, ConceptMastery

def test_media_item_entity():
    item = MediaItem(
        id="m1",
        workspace_id="w1",
        title="Intro to Neural Networks",
        file_path="/videos/nn.mp4",
        media_type=MediaType.VIDEO,
        duration_seconds=120.5
    )
    assert item.status == ProcessingStatus.PENDING
    assert item.duration_seconds == 120.5

def test_timestamp_window_duration():
    window = TimestampWindow(start_time=10.0, end_time=25.5)
    assert window.duration == 15.5

def test_transcript_chunk():
    chunk = TranscriptChunk(
        id="c1",
        media_id="m1",
        workspace_id="w1",
        text="Deep learning uses artificial neural networks.",
        start_time=0.0,
        end_time=5.0,
        chunk_index=0
    )
    assert chunk.start_time == 0.0
    assert "artificial" in chunk.text

def test_workspace_entity():
    ws = Workspace(id="w1", name="Computer Science 101")
    assert ws.name == "Computer Science 101"
    assert ws.media_item_ids == []

def test_user_memory_entity():
    mem = UserMemory(user_id="u1", workspace_id="w1")
    mem.concept_mastery_map["c1"] = ConceptMastery(concept_id="c1", mastery_score=0.85)
    assert mem.concept_mastery_map["c1"].mastery_score == 0.85
