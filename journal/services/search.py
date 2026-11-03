"""Hybrid semantic page search, shared by the dashboard and the MCP server.

Pages are ranked by a weighted blend of summary and content embedding
similarity. The query is embedded through `embed_text` so it always shares a
provider+model with the stored vectors.
"""
import json
import os

import numpy as np
from django.db import connection

from .embeddings import embed_text

EXCERPT_CHARS = int(os.environ.get("RAG_EXCERPT_CHARS", "1500"))

_SEARCH_SQL = """
    SELECT p.id as page_id, pm.summary, pm.date_value,
           p.journal_id, p.page_number, p.ocr_text,
           j.filename,
           string_agg(pmt.tag, ', ') as tags,
           (0.6 * COALESCE(1 - (pse.embedding <=> %s::vector), 0) +
            0.4 * COALESCE(1 - (pce.embedding <=> %s::vector), 0)) as score
    FROM pages p
    JOIN journals j ON j.id = p.journal_id
    LEFT JOIN page_metadata pm ON pm.page_id = p.id AND pm.status = 'done'
    LEFT JOIN page_metadata_tags pmt ON pmt.page_metadata_id = pm.id
    LEFT JOIN page_summary_embeddings pse
      ON pse.page_id = p.id AND pse.status = 'done' AND pse.embedding IS NOT NULL
    LEFT JOIN page_content_embeddings pce
      ON pce.page_id = p.id AND pce.status = 'done' AND pce.embedding IS NOT NULL
    WHERE pse.embedding IS NOT NULL OR pce.embedding IS NOT NULL
    GROUP BY p.id, pm.summary, pm.date_value,
             p.journal_id, p.page_number, p.ocr_text, j.filename,
             pse.embedding, pce.embedding
    ORDER BY score DESC
    LIMIT %s
"""


def embed_query(query: str) -> str:
    """Embed a query string as a pgvector literal, matching the stored space."""
    return json.dumps(np.array(embed_text(query)).tolist())


def retrieve_pages(query_vec: str, limit: int) -> list[dict]:
    """Return the best-matching pages for an embedded query, with full OCR text."""
    with connection.cursor() as cur:
        cur.execute(_SEARCH_SQL, (query_vec, query_vec, limit))
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def excerpt(ocr_text: str | None) -> str:
    """Clip a page's OCR text to the excerpt length used in search results."""
    text = (ocr_text or "").replace("\r", "").strip()
    return text[:EXCERPT_CHARS] + "…" if len(text) > EXCERPT_CHARS else text
