from typing import List, Dict, Any
from app.domain.evaluation.entities import EvaluationMetrics, RetrievalBenchmark

class RAGEvaluator:
    """Automated evaluation framework for retrieval precision, recall, citation groundedness, and latency."""
    
    def evaluate_retrieval(
        self,
        query: str,
        expected_chunk_ids: List[str],
        retrieved_chunk_ids: List[str],
        latency_ms: float = 0.0
    ) -> RetrievalBenchmark:
        if not retrieved_chunk_ids:
            metrics = EvaluationMetrics(retrieval_precision_at_5=0.0, retrieval_recall_at_5=0.0, latency_ms=latency_ms)
            return RetrievalBenchmark(id="eval_0", query=query, expected_chunk_ids=expected_chunk_ids, retrieved_chunk_ids=[], metrics=metrics)

        k = min(5, len(retrieved_chunk_ids))
        top_k_retrieved = set(retrieved_chunk_ids[:k])
        expected_set = set(expected_chunk_ids)

        hits = len(top_k_retrieved.intersection(expected_set))
        precision = hits / k if k > 0 else 0.0
        recall = hits / len(expected_set) if expected_set else 0.0

        metrics = EvaluationMetrics(
            retrieval_precision_at_5=round(precision, 4),
            retrieval_recall_at_5=round(recall, 4),
            latency_ms=latency_ms
        )

        return RetrievalBenchmark(
            id=f"eval_{hash(query) & 0xFFFFFFFF}",
            query=query,
            expected_chunk_ids=expected_chunk_ids,
            retrieved_chunk_ids=retrieved_chunk_ids,
            metrics=metrics
        )

    def evaluate_groundedness(self, answer_text: str, source_context_text: str) -> float:
        """Evaluates citation groundedness ratio by checking phrase overlap."""
        if not answer_text or not source_context_text:
            return 0.0

        answer_words = set(answer_text.lower().split())
        source_words = set(source_context_text.lower().split())

        overlap = len(answer_words.intersection(source_words))
        return round(overlap / len(answer_words), 4) if answer_words else 0.0
