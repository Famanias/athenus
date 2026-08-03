# EVALUATION.md

# Athenus — AI Evaluation Subsystem

---

## Overview

AI features in Athenus are evaluated through an automated, first-class **Evaluation Subsystem** (`app/infrastructure/evaluation/evaluator.py`).

Every retrieval and generation operation is benchmarked against measurable performance metrics to prevent retrieval regression and ensure high citation groundedness.

---

## Evaluation Metrics

1. **Retrieval Precision@K ($K=5$)**:
   $$\text{Precision@K} = \frac{|\text{Retrieved Chunks in Top K} \cap \text{Expected Ground Truth Chunks}|}{K}$$

2. **Retrieval Recall@K ($K=5$)**:
   $$\text{Recall@K} = \frac{|\text{Retrieved Chunks in Top K} \cap \text{Expected Ground Truth Chunks}|}{|\text{Expected Ground Truth Chunks}|}$$

3. **Citation Groundedness Score**:
   Measures the fraction of words/claims in the generated LLM response that directly map to the retrieved video transcript context payload.

4. **Latency & Throughput**:
   Tracks end-to-end execution time ($ms$) for transcription, vector search, re-ranking, and response generation.

---

## Running Evaluation Benchmarks

Run automated evaluation tests via pytest:
```bash
python -m pytest backend/tests/test_evaluation_subsystem.py
```
