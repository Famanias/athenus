import json
import random
import uuid
from datetime import datetime
from typing import List, Optional

from app.domain.ai.capabilities import TextGenerationRequest
from app.domain.ai.service_bus import AIServiceBus
from app.domain.learning.entities import QuizAttempt, QuizContainer, QuizQuestionItem
from app.domain.learning.quiz_generation import (
    ExtractedQuestion,
    build_quiz_prompt,
    generate_quiz_heuristic,
    parse_llm_quiz,
)
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService
from app.infrastructure.db.session import engine
from app.infrastructure.events.event_bus import DomainEvent, EventBus

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


def load_chunks(media_id: str, workspace_id: str) -> List[dict]:
    """Load canonical transcript chunks for a media asset from SQLite."""
    if not engine or not Session or not select:
        return []
    try:
        from app.infrastructure.db.models import TranscriptChunkTable
        with Session(engine) as session:
            stmt = (
                select(TranscriptChunkTable)
                .where(TranscriptChunkTable.media_id == media_id)
                .order_by(TranscriptChunkTable.chunk_index)
            )
            records = session.scalars(stmt).all() if hasattr(session, "scalars") else session.exec(stmt).all()
            return [
                {
                    "id": r.id,
                    "media_id": r.media_id,
                    "workspace_id": r.workspace_id,
                    "text": r.text,
                    "start_time": r.start_time,
                    "end_time": r.end_time,
                    "chunk_index": r.chunk_index,
                }
                for r in records
            ]
    except Exception:
        return []


def _json_loads_or_list(value) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return [p for p in str(value).split(",") if p]


class QuizService:
    """On-demand, versioned comprehension quiz generation grounded in the
    canonical knowledge graph, with concept-balanced sampling and grading."""

    def __init__(
        self,
        graph_service: Optional[KnowledgeGraphService] = None,
        ai_service_bus: Optional[AIServiceBus] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.graph_service = graph_service or KnowledgeGraphService()
        self.ai_service_bus = ai_service_bus
        self.event_bus = event_bus

    # ------------------------------------------------------------------
    # Quiz persistence & versioning
    # ------------------------------------------------------------------
    def _scalars(self, session, statement):
        if hasattr(session, "scalars"):
            return session.scalars(statement).all()
        return session.exec(statement).all()

    def _latest_version(self, workspace_id: str) -> int:
        if not engine or not Session or not select:
            return 0
        try:
            from app.infrastructure.db.models import QuizTable
            with Session(engine) as session:
                stmt = select(QuizTable).where(QuizTable.workspace_id == workspace_id)
                records = self._scalars(session, stmt)
                return max((r.version or 1 for r in records), default=0)
        except Exception:
            return 0

    def _upsert_quiz(
        self,
        quiz_id: str,
        workspace_id: str,
        title: str,
        version: int,
        status: str,
        question_count: int = 0,
        concept_ids: Optional[List[str]] = None,
    ) -> None:
        if not engine or not Session:
            return
        try:
            from app.infrastructure.db.models import QuizTable
            with Session(engine) as session:
                quiz = session.get(QuizTable, quiz_id)
                if quiz:
                    quiz.status = status
                    quiz.question_count = question_count
                    quiz.updated_at = datetime.utcnow()
                else:
                    quiz = QuizTable(
                        id=quiz_id,
                        workspace_id=workspace_id,
                        title=title,
                        version=version,
                        status=status,
                        concept_ids=",".join(concept_ids) if concept_ids else None,
                        question_count=question_count,
                    )
                    session.add(quiz)
                session.commit()
        except Exception:
            pass

    def _concept_dicts(self, workspace_id: str) -> List[dict]:
        concepts = self.graph_service.get_concepts(workspace_id)
        return [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "source_chunk_ids": c.source_chunk_ids,
                "media_id": c.media_id,
                "start_time": c.start_time,
                "end_time": c.end_time,
            }
            for c in concepts
        ]

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    async def _generate_with_llm(self, concepts: List[dict], chunks: List[dict], max_questions: int) -> List[ExtractedQuestion]:
        if not self.ai_service_bus:
            return []
        try:
            text_capability = self.ai_service_bus.get_text_capability()
        except Exception:
            return []
        try:
            gen_res = await text_capability.generate(
                TextGenerationRequest(
                    prompt=build_quiz_prompt(concepts, chunks, max_questions),
                    temperature=0.3,
                    max_tokens=2048,
                )
            )
        except Exception:
            return []
        parsed = parse_llm_quiz(gen_res.text)
        return parsed or []

    async def generate_quiz(
        self,
        workspace_id: str,
        title: str = "Comprehension Quiz",
        max_questions: int = 10,
        force_new_version: bool = False,
    ) -> QuizContainer:
        """Generate (or reuse a cached) versioned quiz for a workspace.

        Version regeneration performs a fresh AI generation request using concept
        rotation instead of cloning previous version questions.
        """
        def update_job(stage: str, progress: int, message: str, status: str = "generating") -> None:
            self.graph_service.upsert_artifact_job(
                job_id=f"quiz_{workspace_id}",
                workspace_id=workspace_id,
                artifact_type="quiz",
                target_key=workspace_id,
                status=status,
                stage=stage,
                progress=progress,
                message=message,
            )

        concept_dicts = self._concept_dicts(workspace_id)
        if not concept_dicts:
            raise ValueError(f"No concepts indexed for workspace {workspace_id}")

        latest = self._latest_version(workspace_id)
        cached = self.get_workspace_quiz(workspace_id, version=latest)
        if cached and cached.status == "ready" and not force_new_version:
            return cached

        version = latest + 1
        quiz_id = f"quiz_{workspace_id}_v{version}"
        self._upsert_quiz(quiz_id, workspace_id, title, version, "generating")

        update_job("collect_context", 20, "Collecting concepts and transcript chunks...")

        concept_ids: List[str] = [c["id"] for c in concept_dicts]
        media_ids: List[str] = []
        for c in concept_dicts:
            if c.get("media_id") and c["media_id"] not in media_ids:
                media_ids.append(c["media_id"])

        all_chunks: List[dict] = []
        for media_id in media_ids:
            all_chunks.extend(load_chunks(media_id, workspace_id))
        seen: set = set()
        chunks = [c for c in all_chunks if not (c["id"] in seen or seen.add(c["id"]))]

        if force_new_version and version > 1:
            selected_concepts, prompt_chunks = self._rotate_concepts_and_chunks(
                workspace_id, concept_dicts, chunks, version
            )
        else:
            selected_concepts = concept_dicts[:12]
            prompt_chunks = chunks

        update_job("llm_generation", 50, "Generating questions with AI model...")
        questions = await self._generate_with_llm(selected_concepts, prompt_chunks, max_questions)
        if not questions:
            questions = generate_quiz_heuristic(selected_concepts, prompt_chunks, max_questions)

        update_job("persist", 85, "Saving questions to database...")
        saved = self._persist_questions(quiz_id, workspace_id, questions, concept_dicts)
        self._upsert_quiz(
            quiz_id, workspace_id, title, version, "ready",
            question_count=saved,
            concept_ids=concept_ids,
        )
        update_job("ready", 100, "Quiz ready.", status="ready")
        return self.get_quiz(quiz_id)

    def _concept_coverage(self, workspace_id: str) -> dict:
        """Map concept_id -> number of questions already generated across all
        prior quiz versions for the workspace."""
        coverage: dict = {}
        if not engine or not Session or not select:
            return coverage
        try:
            from app.infrastructure.db.models import QuizQuestionTable
            with Session(engine) as session:
                stmt = select(QuizQuestionTable).where(QuizQuestionTable.workspace_id == workspace_id)
                records = self._scalars(session, stmt)
                for r in records:
                    if r.concept_id:
                        coverage[r.concept_id] = coverage.get(r.concept_id, 0) + 1
        except Exception:
            pass
        return coverage

    def _rotate_concepts_and_chunks(
        self,
        workspace_id: str,
        concept_dicts: List[dict],
        chunks: List[dict],
        version: int,
        max_concepts: int = 12,
    ):
        """Rotate concept selection toward the least-covered concepts and sample
        transcript chunks from a version-based offset for fresh LLM context."""
        coverage = self._concept_coverage(workspace_id)
        ranked = sorted(
            concept_dicts,
            key=lambda c: (coverage.get(c["id"], 0), c["name"]),
        )
        selected_concepts = ranked[:max_concepts] or ranked
        if chunks:
            offset = (version - 1) % len(chunks)
            rotated_chunks = chunks[offset:] + chunks[:offset]
        else:
            rotated_chunks = chunks
        return selected_concepts, rotated_chunks

    async def evolve_workspace_quiz(
        self,
        workspace_id: str,
        new_concept_ids: List[str],
        title: str = "Auto-evolved Comprehension Quiz",
        target_budget: int = 15,
    ) -> Optional[QuizContainer]:
        """Evolve workspace quiz when new concepts are merged into the Knowledge Graph."""
        if not new_concept_ids:
            return self.get_workspace_quiz(workspace_id)

        all_concept_dicts = self._concept_dicts(workspace_id)
        if not all_concept_dicts:
            return None

        new_concepts = [c for c in all_concept_dicts if c["id"] in new_concept_ids]
        if not new_concepts:
            return self.get_workspace_quiz(workspace_id)

        from app.domain.learning.concept_importance_allocator import (
            ConceptImportanceAllocator,
            ConceptNodeDTO,
            RelationDTO,
        )
        allocator = ConceptImportanceAllocator()

        triples = self.graph_service.get_workspace_triples(workspace_id)
        relation_dtos = [RelationDTO(source_concept=t[0], target_concept=t[2]) for t in triples if len(t) >= 3]
        concept_dtos = [ConceptNodeDTO(id=c["id"], name=c["name"]) for c in new_concepts]

        allocations = allocator.calculate_allocations(concept_dtos, relation_dtos, total_budget=target_budget)

        media_ids: List[str] = []
        for c in new_concepts:
            if c.get("media_id") and c["media_id"] not in media_ids:
                media_ids.append(c["media_id"])

        all_chunks: List[dict] = []
        for media_id in media_ids:
            all_chunks.extend(load_chunks(media_id, workspace_id))
        seen: set = set()
        chunks = [c for c in all_chunks if not (c["id"] in seen or seen.add(c["id"]))]

        new_questions = await self._generate_with_llm(new_concepts, chunks, target_budget)
        if not new_questions:
            new_questions = generate_quiz_heuristic(new_concepts, chunks, target_budget)

        latest_version = self._latest_version(workspace_id)
        new_version = latest_version + 1
        new_quiz_id = f"quiz_{workspace_id}_v{new_version}"
        self._upsert_quiz(new_quiz_id, workspace_id, title, new_version, "generating")

        new_saved_count = self._persist_questions(new_quiz_id, workspace_id, new_questions, new_concepts)
        total_questions_count = new_saved_count

        all_concept_ids = [c["id"] for c in all_concept_dicts]

        self._upsert_quiz(
            new_quiz_id, workspace_id, title, new_version, "ready",
            question_count=total_questions_count,
            concept_ids=all_concept_ids,
        )
        return self.get_quiz(new_quiz_id)

    def _persist_questions(
        self,
        quiz_id: str,
        workspace_id: str,
        questions: List[ExtractedQuestion],
        concepts: List[dict],
    ) -> int:
        if not engine or not Session:
            return 0
        concept_by_name = {c["name"].lower(): c for c in concepts}
        saved = 0
        try:
            from app.infrastructure.db.models import QuizQuestionTable
            with Session(engine) as session:
                for i, q in enumerate(questions):
                    concept = concept_by_name.get((q.concept or "").lower(), {})
                    if not concept and concepts:
                        concept = concepts[i % len(concepts)]
                    qid = f"q_{quiz_id}_{uuid.uuid4().hex[:8]}"
                    session.add(
                        QuizQuestionTable(
                            id=qid,
                            quiz_id=quiz_id,
                            workspace_id=workspace_id,
                            concept_id=concept.get("id"),
                            question_text=q.question_text,
                            options_json=json.dumps(q.options),
                            correct_index=q.correct_index,
                            explanation=q.explanation,
                            media_id=q.media_id or concept.get("media_id"),
                            source_chunk_ids=",".join(q.source_chunk_ids or concept.get("source_chunk_ids", [])) or None,
                            start_time=q.start_time if q.start_time is not None else concept.get("start_time"),
                            end_time=q.end_time if q.end_time is not None else concept.get("end_time"),
                        )
                    )
                    saved += 1
                session.commit()
        except Exception:
            return 0
        return saved

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def get_quiz(self, quiz_id: str) -> Optional[QuizContainer]:
        if not engine or not Session:
            return None
        try:
            from app.infrastructure.db.models import QuizTable
            with Session(engine) as session:
                rec = session.get(QuizTable, quiz_id)
                if not rec:
                    return None
                return self._quiz_from_db(rec)
        except Exception:
            return None

    def get_workspace_quiz(self, workspace_id: str, version: Optional[int] = None) -> Optional[QuizContainer]:
        if not engine or not Session or not select:
            return None
        try:
            from app.infrastructure.db.models import QuizTable
            with Session(engine) as session:
                stmt = select(QuizTable).where(QuizTable.workspace_id == workspace_id)
                if version is not None:
                    stmt = stmt.where(QuizTable.version == version)
                stmt = stmt.order_by(QuizTable.version.desc())
                rec = session.scalars(stmt).first() if hasattr(session, "scalars") else session.exec(stmt).first()
                if not rec:
                    return None
                return self._quiz_from_db(rec)
        except Exception:
            return None

    def list_quizzes(self, workspace_id: str) -> List[QuizContainer]:
        if not engine or not Session or not select:
            return []
        try:
            from app.infrastructure.db.models import QuizTable
            with Session(engine) as session:
                stmt = (
                    select(QuizTable)
                    .where(QuizTable.workspace_id == workspace_id)
                    .order_by(QuizTable.version.desc())
                )
                records = self._scalars(session, stmt)
                return [self._quiz_from_db(r) for r in records]
        except Exception:
            return []

    def get_quiz_questions(self, quiz_id: str) -> List[QuizQuestionItem]:
        if not engine or not Session or not select:
            return []
        try:
            from app.infrastructure.db.models import QuizQuestionTable
            with Session(engine) as session:
                stmt = select(QuizQuestionTable).where(QuizQuestionTable.quiz_id == quiz_id)
                records = self._scalars(session, stmt)
                return [self._question_from_db(r) for r in records]
        except Exception:
            return []

    @staticmethod
    def _quiz_from_db(rec) -> QuizContainer:
        return QuizContainer(
            id=rec.id,
            workspace_id=rec.workspace_id,
            title=rec.title,
            version=rec.version or 1,
            status=rec.status,
            concept_ids=_json_loads_or_list(rec.concept_ids),
            question_count=rec.question_count or 0,
            created_at=rec.created_at,
            updated_at=rec.updated_at,
        )

    @staticmethod
    def _question_from_db(rec) -> QuizQuestionItem:
        options = _json_loads_or_list(rec.options_json)
        return QuizQuestionItem(
            id=rec.id,
            quiz_id=rec.quiz_id,
            workspace_id=rec.workspace_id,
            concept_id=rec.concept_id,
            question_text=rec.question_text,
            options=options,
            correct_index=rec.correct_index,
            explanation=rec.explanation,
            media_id=rec.media_id,
            source_chunk_ids=_json_loads_or_list(rec.source_chunk_ids),
            start_time=rec.start_time,
            end_time=rec.end_time,
        )

    # ------------------------------------------------------------------
    # Grading & attempts
    # ------------------------------------------------------------------
    def grade_attempt(
        self,
        quiz_id: str,
        workspace_id: str,
        answers: dict,
        time_taken: float = 0.0,
    ) -> QuizAttempt:
        """Grade a submission, storing an immutable attempt and emitting an analytics event."""
        quiz = self.get_quiz(quiz_id)
        questions = self.get_quiz_questions(quiz_id)
        if not quiz or not questions:
            raise ValueError("Quiz or questions not found")

        correct = 0
        per_question = {}
        for q in questions:
            user_answer = answers.get(q.id)
            is_correct = user_answer == q.correct_index
            if is_correct:
                correct += 1
            per_question[q.id] = {
                "user_answer": user_answer,
                "correct_index": q.correct_index,
                "is_correct": is_correct,
                "concept_id": q.concept_id,
            }
        score = (correct / len(questions)) * 100.0 if questions else 0.0

        attempt = QuizAttempt(
            id=f"attempt_{uuid.uuid4().hex[:12]}",
            quiz_id=quiz_id,
            workspace_id=workspace_id,
            version=quiz.version,
            score=round(score, 2),
            total_questions=len(questions),
            correct_count=correct,
            answers=per_question,
            time_taken=time_taken,
            created_at=datetime.utcnow(),
        )
        self._persist_attempt(attempt)
        if self.event_bus:
            import asyncio
            try:
                asyncio.get_event_loop().create_task(
                    self.event_bus.publish(
                        DomainEvent(
                            event_type="QuizAttemptEvent",
                            aggregate_id=workspace_id,
                            payload={
                                "workspace_id": workspace_id,
                                "quiz_id": quiz_id,
                                "score": attempt.score,
                                "total_questions": attempt.total_questions,
                                "correct_count": attempt.correct_count,
                                "time_taken": attempt.time_taken,
                                "concept_results": per_question,
                            },
                        )
                    )
                )
            except Exception:
                pass
        return attempt

    def _persist_attempt(self, attempt: QuizAttempt) -> None:
        if not engine or not Session:
            return
        try:
            from app.infrastructure.db.models import QuizAttemptTable
            with Session(engine) as session:
                session.add(
                    QuizAttemptTable(
                        id=attempt.id,
                        quiz_id=attempt.quiz_id,
                        workspace_id=attempt.workspace_id,
                        version=attempt.version,
                        score=attempt.score,
                        total_questions=attempt.total_questions,
                        correct_count=attempt.correct_count,
                        answers_json=json.dumps(attempt.answers) if attempt.answers else None,
                        time_taken=attempt.time_taken,
                        created_at=attempt.created_at,
                    )
                )
                session.commit()
        except Exception:
            pass

    def get_attempts(self, workspace_id: str, limit: int = 20) -> List[QuizAttempt]:
        if not engine or not Session or not select:
            return []
        try:
            from app.infrastructure.db.models import QuizAttemptTable
            with Session(engine) as session:
                stmt = (
                    select(QuizAttemptTable)
                    .where(QuizAttemptTable.workspace_id == workspace_id)
                    .order_by(QuizAttemptTable.created_at.desc())
                    .limit(limit)
                )
                records = self._scalars(session, stmt)
                return [self._attempt_from_db(r) for r in records]
        except Exception:
            return []

    @staticmethod
    def _attempt_from_db(rec) -> QuizAttempt:
        try:
            answers = json.loads(rec.answers_json) if rec.answers_json else None
        except Exception:
            answers = None
        return QuizAttempt(
            id=rec.id,
            quiz_id=rec.quiz_id,
            workspace_id=rec.workspace_id,
            version=rec.version,
            score=rec.score,
            total_questions=rec.total_questions,
            correct_count=rec.correct_count,
            answers=answers,
            time_taken=rec.time_taken,
            created_at=rec.created_at,
        )
