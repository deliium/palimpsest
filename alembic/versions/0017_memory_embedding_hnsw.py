"""Record hybrid-retrieve readiness; HNSW deferred for untyped embeddings.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-04

``memory_traces.embedding`` is ``vector`` without a fixed dimension (Alembic
``0005``). pgvector HNSW/IVFFlat indexes require a typed ``vector(N)`` column,
so this revision intentionally does **not** create an ANN index.

Runtime hybrid retrieve still builds a SQL distance shortlist
(``ORDER BY embedding <=> query LIMIT candidate_cap``) then applies
deterministic ``rank_traces``. ANN index creation is deferred until a
single embedding dimension is pinned project-wide. Append-only triggers
unchanged.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOG = logging.getLogger("alembic.memory_embedding_hnsw")


def upgrade() -> None:
    _LOG.warning(
        "memory_embedding_hnsw_skipped reason_code=vector_column_untyped "
        "revision=%s detail=hnsw_requires_fixed_dimensions",
        revision,
    )


def downgrade() -> None:
    _LOG.info(
        "memory_embedding_hnsw_noop_downgrade revision=%s",
        revision,
    )
