from app.infrastructure.evaluation.evaluator import RAGEvaluator

def test_retrieval_evaluation():
    evaluator = RAGEvaluator()
    benchmark = evaluator.evaluate_retrieval(
        query="What is backpropagation?",
        expected_chunk_ids=["chunk_1", "chunk_2"],
        retrieved_chunk_ids=["chunk_1", "chunk_3", "chunk_4"],
        latency_ms=120.5
    )
    assert benchmark.metrics.retrieval_precision_at_5 == 0.3333
    assert benchmark.metrics.retrieval_recall_at_5 == 0.5
    assert benchmark.metrics.latency_ms == 120.5

def test_groundedness_evaluation():
    evaluator = RAGEvaluator()
    groundedness = evaluator.evaluate_groundedness(
        answer_text="Artificial intelligence transforms education",
        source_context_text="Artificial intelligence transforms modern education methods"
    )
    assert groundedness == 1.0
