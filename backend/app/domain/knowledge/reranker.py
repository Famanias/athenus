from typing import List, Dict, Any

class CrossEncoderReranker:
    """Re-ranking component scoring relevance between query and candidate context chunks."""
    
    def rerank(
        self,
        query: str,
        candidate_chunks: List[Dict[str, Any]],
        top_k: int = 3,
        min_relevance_threshold: float = 0.20
    ) -> List[Dict[str, Any]]:
        if not candidate_chunks:
            return []

        query_words = set(re_tokenize(query))
        scored = []

        for chunk in candidate_chunks:
            chunk_text = chunk.get("text", "")
            chunk_words = set(re_tokenize(chunk_text))

            # Keyword overlap & score density heuristic
            overlap = len(query_words.intersection(chunk_words))
            base_score = chunk.get("score", 0.5)
            bm25_score = chunk.get("bm25_score", 0.0)

            # Combined score
            final_rerank_score = (base_score * 0.4) + (bm25_score * 0.3) + (overlap * 0.3)

            # Zero-Relevance Guard: If zero lexical keyword overlap AND zero BM25 score,
            # dense vector base_score must be >= 0.35 to be considered relevant
            if overlap == 0 and bm25_score == 0 and base_score < 0.35:
                final_rerank_score = 0.0

            if final_rerank_score >= min_relevance_threshold:
                item = dict(chunk)
                item["rerank_score"] = round(final_rerank_score, 4)
                scored.append(item)

        scored.sort(key=lambda x: x["rerank_score"], reverse=True)
        return scored[:top_k]

def re_tokenize(text: str) -> List[str]:
    import re
    return re.findall(r'\w+', text.lower())
