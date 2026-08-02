from typing import List, Dict, Any

class CrossEncoderReranker:
    """Re-ranking component scoring relevance between query and candidate context chunks."""
    
    def rerank(self, query: str, candidate_chunks: List[Dict[str, Any]], top_k: int = 3) -> List[Dict[str, Any]]:
        if not candidate_chunks:
            return []

        query_words = set(re_tokenize(query))
        scored = []

        for chunk in candidate_chunks:
            chunk_text = chunk.get("text", "")
            chunk_words = set(re_tokenize(chunk_text))
            
            # Simple keyword overlap & length density ratio heuristic
            overlap = len(query_words.intersection(chunk_words))
            base_score = chunk.get("score", 0.5)
            bm25_score = chunk.get("bm25_score", 0.0)

            # Combined Reciprocal Rank Fusion / Weighted Score
            final_rerank_score = (base_score * 0.4) + (bm25_score * 0.3) + (overlap * 0.3)
            
            item = dict(chunk)
            item["rerank_score"] = round(final_rerank_score, 4)
            scored.append(item)

        scored.sort(key=lambda x: x["rerank_score"], reverse=True)
        return scored[:top_k]

def re_tokenize(text: str) -> List[str]:
    import re
    return re.findall(r'\w+', text.lower())
