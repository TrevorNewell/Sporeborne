"""
TF-IDF retriever over the Sporeborne GDD -- the RAG piece of the Assignment #4
content pipeline (see content_pipeline.py).

No embeddings, no vector DB, no external API key: the GDD is one ~10-page
markdown file, chunked by section. Hand-rolled TF-IDF + cosine similarity is
the lightest approach that satisfies "show query -> retrieved chunk -> output"
for a corpus this size, and it keeps the pipeline runnable offline with zero
setup, same as crew.py's simulate-mode fallback.
"""

import math
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
GDD_PATH = os.path.join(HERE, "..", "design", "GDD_Sporeborne.md")

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list:
    return _WORD_RE.findall(text.lower())


def _chunk_gdd(markdown_text: str) -> list:
    """
    Splits the GDD into chunks on '## ' section headers (its 11 numbered
    top-level sections). Each chunk keeps its heading as an id, so a
    retrieval result is traceable back to a named GDD section, not just an
    opaque blob of text.
    """
    sections = re.split(r"\n(?=## )", markdown_text)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        heading_match = re.match(r"##\s*(.+)", section)
        title = heading_match.group(1).strip() if heading_match else "Front matter"
        chunks.append({"id": title, "text": section})
    return chunks


class GDDRetriever:
    """TF-IDF retriever over GDD_Sporeborne.md, chunked by section."""

    def __init__(self, gdd_path: str = GDD_PATH):
        with open(gdd_path, encoding="utf-8") as f:
            raw = f.read()
        self.chunks = _chunk_gdd(raw)
        self._doc_tokens = [_tokenize(c["text"]) for c in self.chunks]
        self._n_docs = len(self._doc_tokens)
        self._doc_freq = Counter()
        for tokens in self._doc_tokens:
            self._doc_freq.update(set(tokens))

    def _idf(self, term: str) -> float:
        df = self._doc_freq.get(term, 0)
        return math.log((self._n_docs + 1) / (df + 1)) + 1.0

    def _tfidf_vector(self, tokens: list) -> Counter:
        tf = Counter(tokens)
        return Counter({t: c * self._idf(t) for t, c in tf.items()})

    @staticmethod
    def _cosine(a: Counter, b: Counter) -> float:
        common = set(a) & set(b)
        dot = sum(a[t] * b[t] for t in common)
        norm_a = math.sqrt(sum(v * v for v in a.values()))
        norm_b = math.sqrt(sum(v * v for v in b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def search(self, query: str, k: int = 3) -> list:
        """Returns the top-k GDD chunks for `query`: [{id, text, score}, ...]."""
        query_vec = self._tfidf_vector(_tokenize(query))
        scored = []
        for chunk, tokens in zip(self.chunks, self._doc_tokens):
            doc_vec = self._tfidf_vector(tokens)
            score = self._cosine(query_vec, doc_vec)
            scored.append({"id": chunk["id"], "text": chunk["text"], "score": round(score, 4)})
        scored.sort(key=lambda c: c["score"], reverse=True)
        return scored[:k]
