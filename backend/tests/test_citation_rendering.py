import pytest
from app.domain.knowledge.citation_parser import parse_chat_citations
from app.presentation.api.v1.chat import CitationDTO


def test_parse_chat_citations_video_timestamps():
    text = "As stated in [01:15 - 01:45], neural networks rely on gradient descent."
    citations = parse_chat_citations(text)

    assert len(citations) == 1
    assert citations[0]["source_type"] == "video"
    assert citations[0]["start_time"] == 75.0
    assert citations[0]["end_time"] == 105.0


def test_parse_chat_citations_document_pages():
    text = "The theorem is proved in [Document Page 12 (Proof Chapter)] and [Page 15]."
    citations = parse_chat_citations(text)

    assert len(citations) == 2
    assert citations[0]["source_type"] == "pdf"
    assert citations[0]["page_number"] == 12
    assert citations[0]["section_title"] == "Proof Chapter"

    assert citations[1]["source_type"] == "pdf"
    assert citations[1]["page_number"] == 15


def test_citation_dto_document_serialization():
    dto = CitationDTO(
        chunk_id="doc_chunk_1",
        source_type="pdf",
        page_number=5,
        section_title="Intro",
        text="Sample document chunk text",
        location={"type": "document", "page": 5, "section": "Intro"},
    )
    dump = dto.model_dump()

    assert dump["source_type"] == "pdf"
    assert dump["page_number"] == 5
    assert dump["section_title"] == "Intro"
    assert dump["location"]["page"] == 5
