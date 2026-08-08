import asyncio
import uuid

from app.domain.ai.capabilities import TextGenerationResponse
from app.domain.learning.quiz_generation import (
    build_quiz_prompt,
    generate_quiz_heuristic,
    parse_llm_quiz,
)
from app.domain.learning.quiz_service import QuizService
from app.domain.knowledge.entities import ConceptNode
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService
from app.infrastructure.db.session import init_db


class FakeQuizCapability:
    """Fake text capability that captures prompts and returns a parseable quiz."""

    def __init__(self):
        self.prompts = []

    async def generate(self, request):
        self.prompts.append(request.prompt)
        return TextGenerationResponse(
            text=(
                '{"questions": [{"question_text": "Sample question?", '
                '"options": ["A", "B"], "correct_index": 0, '
                '"explanation": "Because.", "concept": "Overfitting"}]}'
            )
        )


class FakeQuizBus:
    """Minimal fake AIServiceBus exposing only get_text_capability()."""

    def __init__(self, capability):
        self._capability = capability

    def get_text_capability(self):
        return self._capability



def _seed_graph(workspace_id: str) -> None:
    service = KnowledgeGraphService()
    for idx, (name, desc) in enumerate(
        [
            ("Overfitting", "Model memorizes training data and fails on unseen data."),
            ("Regularization", "Techniques reducing overfitting by penalizing complexity."),
            ("Backpropagation", "Gradient computation through the network via the chain rule."),
            ("Learning Rate", "Step size controlling parameter updates during training."),
        ]
    ):
        service.add_concept(
            ConceptNode(
                id=f"{workspace_id}_c{idx}_{uuid.uuid4().hex[:6]}",
                workspace_id=workspace_id,
                name=name,
                description=desc,
            )
        )


# ---------------------------------------------------------------------------
# Quiz generation prompt & parsing
# ---------------------------------------------------------------------------
def test_quiz_prompt_contains_concepts_and_chunks():
    concepts = [{"name": "Overfitting", "description": "Memorizes training data.", "source_chunk_ids": ["chunk_0"]}]
    chunks = [{"id": "chunk_0", "text": "Overfitting occurs when...", "start_time": 0.0, "end_time": 10.0}]
    prompt = build_quiz_prompt(concepts, chunks, max_questions=5)
    assert "Overfitting" in prompt
    assert "chunk_0" in prompt
    assert "questions" in prompt


def test_parse_llm_quiz():
    raw = '{"questions": [{"question_text": "What is overfitting?", "options": ["A", "B", "C", "D"], "correct_index": 2, "explanation": "Because...", "concept": "Overfitting", "source_chunk_ids": ["chunk_0"]}]}'
    parsed = parse_llm_quiz(raw)
    assert parsed is not None
    assert len(parsed) == 1
    q = parsed[0]
    assert q.correct_index == 2
    assert q.concept == "Overfitting"
    assert q.options == ["A", "B", "C", "D"]


def test_parse_llm_quiz_invalid_returns_none():
    assert parse_llm_quiz("not json") is None
    assert parse_llm_quiz(None) is None


def test_quiz_heuristic_concept_balanced():
    concepts = [
        {"id": "1", "name": "Overfitting", "description": "Memorizes training data.", "source_chunk_ids": ["c0"]},
        {"id": "2", "name": "Regularization", "description": "Reduces overfitting.", "source_chunk_ids": ["c1"]},
        {"id": "3", "name": "Backpropagation", "description": "Chain rule gradients.", "source_chunk_ids": ["c2"]},
    ]
    chunks = [
        {"id": "c0", "text": "Overfitting is bad.", "media_id": "m1", "start_time": 0.0, "end_time": 5.0},
        {"id": "c1", "text": "Regularization helps.", "media_id": "m1", "start_time": 5.0, "end_time": 10.0},
        {"id": "c2", "text": "Backpropagation uses chain rule.", "media_id": "m1", "start_time": 10.0, "end_time": 15.0},
    ]
    questions = generate_quiz_heuristic(concepts, chunks, max_questions=10)
    assert len(questions) == len(concepts)
    covered = {q.concept for q in questions}
    assert covered == {"Overfitting", "Regularization", "Backpropagation"}
    for q in questions:
        assert len(q.options) >= 2
        assert 0 <= q.correct_index < len(q.options)


# ---------------------------------------------------------------------------
# Quiz service: versioned generation, grading
# ---------------------------------------------------------------------------
def test_generate_quiz_heuristic_fallback():
    init_db()
    ws = f"ws_quiz_{uuid.uuid4().hex[:8]}"
    _seed_graph(ws)
    service = QuizService()
    quiz = asyncio.run(service.generate_quiz(workspace_id=ws, max_questions=5))
    assert quiz.status == "ready"
    assert quiz.version == 1
    assert quiz.question_count >= 1
    questions = service.get_quiz_questions(quiz.id)
    assert len(questions) >= 1
    assert questions[0].workspace_id == ws


def test_quiz_caching_and_versioning():
    init_db()
    ws = f"ws_quizver_{uuid.uuid4().hex[:8]}"
    _seed_graph(ws)
    service = QuizService()
    quiz_v1 = asyncio.run(service.generate_quiz(workspace_id=ws))
    cached = asyncio.run(service.generate_quiz(workspace_id=ws))
    assert cached.id == quiz_v1.id
    assert cached.version == 1
    quiz_v2 = asyncio.run(service.generate_quiz(workspace_id=ws, force_new_version=True))
    assert quiz_v2.version == 2
    assert quiz_v2.id != quiz_v1.id
    quizzes = service.list_quizzes(ws)
    assert len(quizzes) == 2


def test_grade_attempt():
    init_db()
    ws = f"ws_grad_{uuid.uuid4().hex[:8]}"
    _seed_graph(ws)
    service = QuizService()
    quiz = asyncio.run(service.generate_quiz(workspace_id=ws, max_questions=3))
    questions = service.get_quiz_questions(quiz.id)
    assert questions

    answers = {}
    for i, q in enumerate(questions):
        answers[q.id] = q.correct_index if i == 0 else (q.correct_index + 1) % len(q.options)

    attempt = service.grade_attempt(quiz.id, ws, answers, time_taken=42.5)
    assert attempt.quiz_id == quiz.id
    assert attempt.total_questions == len(questions)
    assert attempt.correct_count == 1
    assert attempt.score == round((1 / len(questions)) * 100.0, 2)
    assert attempt.time_taken == 42.5

    attempts = service.get_attempts(ws)
    assert len(attempts) == 1
    assert attempts[0].correct_count == 1


def test_generation_prompt_carries_version():
    init_db()
    ws = f"ws_prompt_{uuid.uuid4().hex[:8]}"
    _seed_graph(ws)
    capability = FakeQuizCapability()
    service = QuizService(ai_service_bus=FakeQuizBus(capability))
    v1 = asyncio.run(service.generate_quiz(workspace_id=ws, max_questions=2))
    v2 = asyncio.run(service.generate_quiz(workspace_id=ws, force_new_version=True, max_questions=2))
    assert "Quiz Version 1" in capability.prompts[0]
    assert "Quiz Version 2" in capability.prompts[-1]
    assert v2.version == 2
