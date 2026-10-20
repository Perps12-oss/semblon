"""BM25 over stored OCR strings. Derived at query time. No new table."""

from __future__ import annotations

import math
import re

_TOKEN = re.compile(r"[a-z0-9]{2,}", re.IGNORECASE)


def tokenize(text: str | None) -> list[str]:
    return [token.lower() for token in _TOKEN.findall(str(text or ""))]


def bm25_rank(
    documents: list[tuple[str, str]],
    query: str,
    *,
    limit: int = 50,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[tuple[str, float]]:
    """Rank (doc_id, text) pairs. Duplicate ids keep the best score."""
    q_tokens = tokenize(query)
    if not q_tokens or not documents:
        return []
    bag: list[tuple[str, list[str]]] = []
    for doc_id, text in documents:
        tokens = tokenize(text)
        if tokens:
            bag.append((str(doc_id), tokens))
    if not bag:
        return []
    n = len(bag)
    avg_len = sum(len(tokens) for _doc, tokens in bag) / n
    df: dict[str, int] = {}
    for _doc, tokens in bag:
        for token in set(tokens):
            df[token] = df.get(token, 0) + 1
    idf = {
        token: math.log(1.0 + (n - count + 0.5) / (count + 0.5))
        for token, count in df.items()
    }
    best: dict[str, float] = {}
    order: list[str] = []
    for doc_id, tokens in bag:
        length = len(tokens)
        tf: dict[str, int] = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1
        score = 0.0
        for token in q_tokens:
            if token not in tf:
                continue
            freq = tf[token]
            denom = freq + k1 * (1.0 - b + b * length / avg_len)
            score += idf.get(token, 0.0) * (freq * (k1 + 1.0) / denom)
        if score <= 0:
            continue
        prev = best.get(doc_id)
        if prev is None:
            best[doc_id] = score
            order.append(doc_id)
        elif score > prev:
            best[doc_id] = score
    ranked = sorted(order, key=lambda key: -best[key])[: max(1, int(limit))]
    return [(key, best[key]) for key in ranked]
