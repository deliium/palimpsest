"""Alembic revision for durable run control and experiment membership.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-22

Adds run_control_states + run_lifecycle_transitions, backfills legacy runs as
configuration-unavailable, reconciles experiment_assignments with
experiment_runs, drops orphan assignment/result rows before adding the
simulation_runs foreign key on assignments.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOG = logging.getLogger("alembic.v1_run_control")
_STABLE_ID_LEN = 128
_SHA256_HEX_LEN = 64
_APPEND_ONLY_TABLES: tuple[str, ...] = ("run_lifecycle_transitions",)


def upgrade() -> None:
    _LOG.info(
        "v1_run_control_migration_start",
        extra={"revision": revision, "operation": "upgrade"},
    )

    # Orphan cleanup before FK: assignments/results without a simulation run.
    orphan_results = op.get_bind().execute(
        text(
            """
            DELETE FROM experiment_results r
            WHERE NOT EXISTS (
                SELECT 1 FROM simulation_runs s WHERE s.run_id = r.run_id
            )
            RETURNING r.run_id
            """
        )
    )
    orphan_result_count = len(orphan_results.fetchall())
    if orphan_result_count:
        _LOG.warning(
            "legacy_orphan_experiment_results_removed",
            extra={"revision": revision, "count": orphan_result_count},
        )

    orphan_assignments = op.get_bind().execute(
        text(
            """
            DELETE FROM experiment_assignments a
            WHERE NOT EXISTS (
                SELECT 1 FROM simulation_runs s WHERE s.run_id = a.run_id
            )
            RETURNING a.run_id
            """
        )
    )
    orphan_assignment_count = len(orphan_assignments.fetchall())
    if orphan_assignment_count:
        _LOG.warning(
            "legacy_orphan_experiment_assignments_removed",
            extra={"revision": revision, "count": orphan_assignment_count},
        )

    op.execute(
        """
        ALTER TABLE experiment_assignments
        ADD CONSTRAINT fk_experiment_assignments_run
        FOREIGN KEY (run_id)
        REFERENCES simulation_runs (run_id)
        ON DELETE RESTRICT
        """
    )

    # Ensure legacy experiments rows exist for definition-only IDs so
    # experiment_runs (canonical membership mirror) can be populated.
    op.execute(
        """
        INSERT INTO experiments (experiment_id, label)
        SELECT d.experiment_id, d.experiment_id
        FROM experiment_definitions d
        WHERE NOT EXISTS (
            SELECT 1 FROM experiments e WHERE e.experiment_id = d.experiment_id
        )
        """
    )

    # Canonical membership mirror: backfill experiment_runs from assignments.
    # Prefer assignment as source of truth; leave legacy-only experiment_runs.
    op.execute(
        """
        INSERT INTO experiment_runs (experiment_id, run_id, ordinal)
        SELECT
            a.experiment_id,
            a.run_id,
            COALESCE(base.max_ordinal, -1)
                + ROW_NUMBER() OVER (
                    PARTITION BY a.experiment_id
                    ORDER BY a.created_ordinal
                )
        FROM experiment_assignments a
        LEFT JOIN LATERAL (
            SELECT MAX(er.ordinal) AS max_ordinal
            FROM experiment_runs er
            WHERE er.experiment_id = a.experiment_id
        ) AS base ON TRUE
        WHERE NOT EXISTS (
            SELECT 1
            FROM experiment_runs er
            WHERE er.experiment_id = a.experiment_id
              AND er.run_id = a.run_id
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE run_control_states (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL PRIMARY KEY,
            lifecycle_state VARCHAR(32) NOT NULL,
            lifecycle_version BIGINT NOT NULL,
            config_availability VARCHAR(32) NOT NULL,
            config_schema_version VARCHAR(64),
            config_fingerprint CHAR({_SHA256_HEX_LEN}),
            config_payload BYTEA,
            ticks_committed BIGINT NOT NULL DEFAULT 0,
            progress_cursor BIGINT NOT NULL DEFAULT 0,
            lease_id VARCHAR({_STABLE_ID_LEN}),
            lease_owner_id VARCHAR({_STABLE_ID_LEN}),
            lease_claimed_at_unix_ms BIGINT,
            lease_heartbeat_at_unix_ms BIGINT,
            lease_expires_at_unix_ms BIGINT,
            terminal_reason_code VARCHAR(64),
            CONSTRAINT fk_run_control_states_run
                FOREIGN KEY (run_id)
                REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_run_control_lifecycle_state
                CHECK (lifecycle_state IN (
                    'configured','ready','paused','starting','running','stopping',
                    'completed','failed','fenced','recovery-required','interrupted'
                )),
            CONSTRAINT ck_run_control_config_availability
                CHECK (config_availability IN ('available','unavailable')),
            CONSTRAINT ck_run_control_lifecycle_version
                CHECK (lifecycle_version >= 0),
            CONSTRAINT ck_run_control_progress_nonneg
                CHECK (ticks_committed >= 0 AND progress_cursor >= 0),
            CONSTRAINT ck_run_control_config_envelope
                CHECK (
                    (
                        config_availability = 'unavailable'
                        AND config_schema_version IS NULL
                        AND config_fingerprint IS NULL
                        AND config_payload IS NULL
                    ) OR (
                        config_availability = 'available'
                        AND config_schema_version IS NOT NULL
                        AND config_fingerprint IS NOT NULL
                        AND config_payload IS NOT NULL
                    )
                ),
            CONSTRAINT ck_run_control_config_fingerprint
                CHECK (
                    config_fingerprint IS NULL
                    OR char_length(config_fingerprint) = {_SHA256_HEX_LEN}
                )
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_run_control_states_lifecycle "
        "ON run_control_states (lifecycle_state)"
    )
    op.execute(
        "CREATE INDEX ix_run_control_states_lease "
        "ON run_control_states (lease_id)"
    )

    # Legacy runs: explicit configuration-unavailable (never fabricate config).
    inserted = op.get_bind().execute(
        text(
            """
            INSERT INTO run_control_states (
                run_id,
                lifecycle_state,
                lifecycle_version,
                config_availability,
                ticks_committed,
                progress_cursor
            )
            SELECT
                s.run_id,
                'configured',
                0,
                'unavailable',
                COALESCE(
                    (
                        SELECT MAX(t.tick) + 1
                        FROM tick_commits t
                        WHERE t.run_id = s.run_id
                    ),
                    0
                ),
                COALESCE(
                    (
                        SELECT MAX(t.tick) + 1
                        FROM tick_commits t
                        WHERE t.run_id = s.run_id
                    ),
                    0
                )
            FROM simulation_runs s
            RETURNING run_id
            """
        )
    )
    legacy_count = len(inserted.fetchall())
    _LOG.warning(
        "legacy_runs_marked_configuration_unavailable",
        extra={"revision": revision, "count": legacy_count},
    )

    op.execute(
        f"""
        CREATE TABLE run_lifecycle_transitions (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            from_state VARCHAR(32) NOT NULL,
            to_state VARCHAR(32) NOT NULL,
            expected_version BIGINT NOT NULL,
            resulting_version BIGINT NOT NULL,
            reason_code VARCHAR(64) NOT NULL,
            operation_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            created_ordinal BIGSERIAL NOT NULL,
            PRIMARY KEY (run_id, resulting_version),
            CONSTRAINT fk_run_lifecycle_transitions_run
                FOREIGN KEY (run_id)
                REFERENCES run_control_states (run_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_run_lifecycle_transition_versions
                CHECK (
                    expected_version >= 0
                    AND resulting_version = expected_version + 1
                )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_run_lifecycle_transitions_ordinal
            ON run_lifecycle_transitions (created_ordinal)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_run_lifecycle_transitions_operation
            ON run_lifecycle_transitions (operation_id)
        """
    )
    for table in _APPEND_ONLY_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_reject_update
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE PROCEDURE reject_history_mutation()
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_reject_delete
            BEFORE DELETE ON {table}
            FOR EACH ROW
            EXECUTE PROCEDURE reject_history_mutation()
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_reject_truncate
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT
            EXECUTE PROCEDURE reject_history_mutation()
            """
        )

    _LOG.info(
        "v1_run_control_migration_complete",
        extra={"revision": revision, "operation": "upgrade"},
    )


def downgrade() -> None:
    _LOG.info(
        "v1_run_control_migration_start",
        extra={"revision": revision, "operation": "downgrade"},
    )
    for table in reversed(_APPEND_ONLY_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_reject_update ON {table}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_reject_delete ON {table}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_reject_truncate ON {table}")
    op.execute("DROP TABLE IF EXISTS run_lifecycle_transitions")
    op.execute("DROP TABLE IF EXISTS run_control_states")
    op.execute(
        "ALTER TABLE experiment_assignments "
        "DROP CONSTRAINT IF EXISTS fk_experiment_assignments_run"
    )
    _LOG.info(
        "v1_run_control_migration_complete",
        extra={"revision": revision, "operation": "downgrade"},
    )
