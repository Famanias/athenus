import math
import re
from typing import List, Dict, Any

class BM25Retriever:
    """Lightweight BM25 Sparse Search Retriever for keyword context matching."""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r'\w+', text.lower())

    def rank(self, query: str, documents: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        if not documents:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return documents[:top_k]

        doc_tokens_list = [self._tokenize(doc.get("text", "")) for doc in documents]
        doc_lengths = [len(tokens) for tokens in doc_tokens_list]
        avg_doc_len = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 1.0
        num_docs = len(documents)

        # Document Frequency
        df: Dict[str, int] = {}
        for tokens in doc_tokens_list:
            unique_tokens = set(tokens)
            for token in unique_tokens:
                df[token] = df.get(token, 0) + 1

        scores = []
        for idx, (doc, tokens) in enumerate(zip(documents, doc_tokens_list)):
            doc_len = doc_lengths[idx]
            score = 0.0
            token_counts: Dict[str, int] = {}
            for t in tokens:
                token_counts[t] = token_counts.get(t, 0) + 1

            for q_token in query_tokens:
                if q_token not in token_counts:
                    continue
                tf = token_counts[q_token]
                doc_freq = df.get(q_token, 0)
                idf = math.log((num_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / avg_doc_len))
                score += idf * (numerator / denominator)

            scored_doc = dict(doc)
            scored_doc["bm25_score"] = score
            scores.append(scored_doc)

        scores.sort(key=lambda x: x["bm25_score"], reverse=True)
        return scores[:top_k]

    def search_fts5(self, workspace_id: str, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Queries SQLite transcript_chunks_fts using native FTS5 BM25 search across full corpus."""
        from app.infrastructure.db.session import engine
        if not engine:
            return []
        tokens = self._tokenize(query)
        if not tokens:
            return []
        fts_query = " OR ".join(tokens)
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                rows = conn.execute(
                    text("""
                        SELECT tc.id, tc.media_id, tc.workspace_id, tc.text, tc.start_time, tc.end_time,
                               tc.chunk_index, tc.word_count, m.title as media_title
                        FROM transcript_chunks_fts fts
                        JOIN transcript_chunks tc ON fts.chunk_id = tc.id
                        LEFT JOIN media_items m ON tc.media_id = m.id
                        WHERE fts.workspace_id = :ws AND transcript_chunks_fts MATCH :q
                        ORDER BY bm25(transcript_chunks_fts) ASC
                        LIMIT :limit;
                    """),
                    {"ws": workspace_id, "q": fts_query, "limit": top_k}
                ).mappings().all()
                results = []
                for idx, r in enumerate(rows):
                    dict_row = dict(r)
                    dict_row["bm25_score"] = round(1.0 / (idx + 1.0), 4)
                    results.append(dict_row)
                return results
        except Exception:
            return []
