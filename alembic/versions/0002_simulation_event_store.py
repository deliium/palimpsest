"""Append-only simulation event store schema.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-16

Runtime role guidance (document only; not applied by this revision):
grant SELECT, INSERT on authoritative history tables to the application role;
do not grant UPDATE, DELETE, or TRUNCATE. Triggers below reject those
operations even if a privileged role attempts them.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUTHORITATIVE_TABLES: tuple[str, ...] = (
    "experiments",
    "experiment_runs",
    "simulation_runs",
    "tick_commits",
    "world_events",
    "world_snapshots",
    "snapshot_locations",
    "snapshot_registrations",
    "snapshot_bodies",
    "snapshot_inventory",
    "snapshot_items",
    "snapshot_resources",
    "snapshot_weather",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE experiments (
            experiment_id VARCHAR(128) NOT NULL,
            label TEXT NOT NULL,
            CONSTRAINT pk_experiments PRIMARY KEY (experiment_id),
            CONSTRAINT ck_experiments_label_len
                CHECK (char_length(label) BETWEEN 1 AND 256)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE world_snapshots (
            snapshot_id VARCHAR(128) NOT NULL,
            run_id VARCHAR(128) NOT NULL,
            world_id VARCHAR(128) NOT NULL,
            seed NUMERIC NOT NULL,
            config_seed NUMERIC NOT NULL,
            next_tick BIGINT NOT NULL,
            revision BIGINT NOT NULL,
            event_schema_version INTEGER NOT NULL,
            projector_version TEXT NOT NULL,
            persistence_codec_version TEXT NOT NULL,
            derivation_version TEXT NOT NULL,
            integrity_hash VARCHAR(64) NOT NULL,
            predecessor_commit_hash VARCHAR(64),
            canonical_payload JSONB NOT NULL,
            CONSTRAINT pk_world_snapshots PRIMARY KEY (snapshot_id),
            CONSTRAINT uq_world_snapshots_run UNIQUE (run_id, snapshot_id),
            CONSTRAINT ck_world_snapshots_seed_nonneg CHECK (seed >= 0),
            CONSTRAINT ck_world_snapshots_config_seed_nonneg CHECK (config_seed >= 0),
            CONSTRAINT ck_world_snapshots_seed_matches_config
                CHECK (seed = config_seed),
            CONSTRAINT ck_world_snapshots_next_tick_nonneg CHECK (next_tick >= 0),
            CONSTRAINT ck_world_snapshots_revision_nonneg CHECK (revision >= 0),
            CONSTRAINT ck_world_snapshots_event_schema_nonneg
                CHECK (event_schema_version >= 0),
            CONSTRAINT ck_world_snapshots_integrity_hash_len
                CHECK (char_length(integrity_hash) = 64),
            CONSTRAINT ck_world_snapshots_integrity_hash_hex
                CHECK (integrity_hash ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_world_snapshots_predecessor_hash_hex
                CHECK (
                    predecessor_commit_hash IS NULL
                    OR (
                        char_length(predecessor_commit_hash) = 64
                        AND predecessor_commit_hash ~ '^[0-9a-f]{64}$'
                    )
                )
        )
        """
    )
    op.execute(
        """
        CREATE TABLE simulation_runs (
            run_id VARCHAR(128) NOT NULL,
            world_id VARCHAR(128) NOT NULL,
            seed NUMERIC NOT NULL,
            config_seed NUMERIC NOT NULL,
            derivation_version TEXT NOT NULL,
            event_schema_version INTEGER NOT NULL,
            projector_version TEXT NOT NULL,
            persistence_codec_version TEXT NOT NULL,
            bootstrap_snapshot_id VARCHAR(128) NOT NULL,
            CONSTRAINT pk_simulation_runs PRIMARY KEY (run_id),
            CONSTRAINT ck_simulation_runs_seed_nonneg CHECK (seed >= 0),
            CONSTRAINT ck_simulation_runs_config_seed_nonneg CHECK (config_seed >= 0),
            CONSTRAINT ck_simulation_runs_seed_matches_config
                CHECK (seed = config_seed),
            CONSTRAINT ck_simulation_runs_event_schema_nonneg
                CHECK (event_schema_version >= 0),
            CONSTRAINT ck_simulation_runs_bootstrap_id_nonempty
                CHECK (char_length(bootstrap_snapshot_id) > 0)
        )
        """
    )
    op.execute(
        """
        ALTER TABLE world_snapshots
            ADD CONSTRAINT fk_world_snapshots_run
            FOREIGN KEY (run_id) REFERENCES simulation_runs (run_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        """
    )
    op.execute(
        """
        ALTER TABLE simulation_runs
            ADD CONSTRAINT fk_simulation_runs_bootstrap
            FOREIGN KEY (run_id, bootstrap_snapshot_id)
            REFERENCES world_snapshots (run_id, snapshot_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        """
    )
    op.execute(
        "CREATE INDEX ix_simulation_runs_world_id ON simulation_runs (world_id)"
    )
    op.execute(
        """
        CREATE INDEX ix_world_snapshots_run_next_tick
            ON world_snapshots (run_id, next_tick)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_world_snapshots_run_revision
            ON world_snapshots (run_id, revision)
        """
    )
    op.execute(
        """
        CREATE TABLE experiment_runs (
            experiment_id VARCHAR(128) NOT NULL,
            run_id VARCHAR(128) NOT NULL,
            ordinal INTEGER NOT NULL DEFAULT 0,
            CONSTRAINT pk_experiment_runs PRIMARY KEY (experiment_id, run_id),
            CONSTRAINT fk_experiment_runs_experiment
                FOREIGN KEY (experiment_id) REFERENCES experiments (experiment_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_experiment_runs_run
                FOREIGN KEY (run_id) REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_experiment_runs_ordinal_nonneg CHECK (ordinal >= 0),
            CONSTRAINT uq_experiment_runs_ordinal UNIQUE (experiment_id, ordinal)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_experiment_runs_run_id ON experiment_runs (run_id)"
    )
    op.execute(
        """
        CREATE TABLE tick_commits (
            run_id VARCHAR(128) NOT NULL,
            tick BIGINT NOT NULL,
            resulting_tick BIGINT NOT NULL,
            base_revision BIGINT NOT NULL,
            resulting_revision BIGINT NOT NULL,
            predecessor_commit_hash VARCHAR(64),
            commit_hash VARCHAR(64) NOT NULL,
            idempotency_key VARCHAR(128) NOT NULL,
            event_count INTEGER NOT NULL,
            payload_hash VARCHAR(64) NOT NULL,
            snapshot_id VARCHAR(128),
            CONSTRAINT pk_tick_commits PRIMARY KEY (run_id, tick),
            CONSTRAINT fk_tick_commits_run
                FOREIGN KEY (run_id) REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_tick_commits_snapshot
                FOREIGN KEY (run_id, snapshot_id)
                REFERENCES world_snapshots (run_id, snapshot_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_tick_commits_tick_nonneg CHECK (tick >= 0),
            CONSTRAINT ck_tick_commits_resulting_tick_succ
                CHECK (resulting_tick = tick + 1),
            CONSTRAINT ck_tick_commits_base_revision_nonneg
                CHECK (base_revision >= 0),
            CONSTRAINT ck_tick_commits_resulting_revision_nonneg
                CHECK (resulting_revision >= 0),
            CONSTRAINT ck_tick_commits_revision_monotonic
                CHECK (resulting_revision >= base_revision),
            CONSTRAINT ck_tick_commits_revision_delta
                CHECK (resulting_revision - base_revision BETWEEN 0 AND 1),
            CONSTRAINT ck_tick_commits_event_count_nonneg CHECK (event_count >= 0),
            CONSTRAINT ck_tick_commits_commit_hash_len
                CHECK (char_length(commit_hash) = 64),
            CONSTRAINT ck_tick_commits_commit_hash_hex
                CHECK (commit_hash ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_tick_commits_payload_hash_len
                CHECK (char_length(payload_hash) = 64),
            CONSTRAINT ck_tick_commits_payload_hash_hex
                CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_tick_commits_predecessor_hash_hex
                CHECK (
                    predecessor_commit_hash IS NULL
                    OR (
                        char_length(predecessor_commit_hash) = 64
                        AND predecessor_commit_hash ~ '^[0-9a-f]{64}$'
                    )
                ),
            CONSTRAINT uq_tick_commits_idem UNIQUE (run_id, idempotency_key),
            CONSTRAINT uq_tick_commits_hash UNIQUE (run_id, commit_hash)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_tick_commits_run_revision
            ON tick_commits (run_id, resulting_revision)
        """
    )
    op.execute(
        """
        CREATE TABLE world_events (
            run_id VARCHAR(128) NOT NULL,
            tick BIGINT NOT NULL,
            sequence INTEGER NOT NULL,
            event_id VARCHAR(128) NOT NULL,
            world_id VARCHAR(128) NOT NULL,
            request_id VARCHAR(128) NOT NULL,
            resulting_revision BIGINT NOT NULL,
            schema_version INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            actor_id VARCHAR(128),
            target_id VARCHAR(128),
            details JSONB NOT NULL,
            payload_hash VARCHAR(64) NOT NULL,
            CONSTRAINT pk_world_events PRIMARY KEY (run_id, tick, sequence),
            CONSTRAINT uq_world_events_event_id UNIQUE (event_id),
            CONSTRAINT fk_world_events_tick
                FOREIGN KEY (run_id, tick)
                REFERENCES tick_commits (run_id, tick)
                ON DELETE RESTRICT,
            CONSTRAINT ck_world_events_tick_nonneg CHECK (tick >= 0),
            CONSTRAINT ck_world_events_sequence_nonneg CHECK (sequence >= 0),
            CONSTRAINT ck_world_events_resulting_revision_nonneg
                CHECK (resulting_revision >= 0),
            CONSTRAINT ck_world_events_schema_version_nonneg
                CHECK (schema_version >= 0),
            CONSTRAINT ck_world_events_payload_hash_len
                CHECK (char_length(payload_hash) = 64),
            CONSTRAINT ck_world_events_payload_hash_hex
                CHECK (payload_hash ~ '^[0-9a-f]{64}$')
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_world_events_run_tick_revision
            ON world_events (run_id, tick, resulting_revision)
        """
    )
    op.execute("CREATE INDEX ix_world_events_actor_id ON world_events (actor_id)")
    op.execute("CREATE INDEX ix_world_events_target_id ON world_events (target_id)")
    op.execute(
        "CREATE INDEX ix_world_events_event_type ON world_events (event_type)"
    )
    op.execute(
        """
        CREATE TABLE snapshot_locations (
            run_id VARCHAR(128) NOT NULL,
            snapshot_id VARCHAR(128) NOT NULL,
            entity_id VARCHAR(128) NOT NULL,
            name TEXT NOT NULL,
            CONSTRAINT pk_snapshot_locations
                PRIMARY KEY (run_id, snapshot_id, entity_id),
            CONSTRAINT fk_snapshot_locations_snapshot
                FOREIGN KEY (run_id, snapshot_id)
                REFERENCES world_snapshots (run_id, snapshot_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_snapshot_locations_name_nonempty
                CHECK (char_length(name) > 0)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_snapshot_locations_entity ON snapshot_locations (entity_id)"
    )
    op.execute(
        """
        CREATE TABLE snapshot_registrations (
            run_id VARCHAR(128) NOT NULL,
            snapshot_id VARCHAR(128) NOT NULL,
            ordinal INTEGER NOT NULL,
            agent_id VARCHAR(128) NOT NULL,
            entity_id VARCHAR(128) NOT NULL,
            CONSTRAINT pk_snapshot_registrations
                PRIMARY KEY (run_id, snapshot_id, ordinal),
            CONSTRAINT fk_snapshot_registrations_snapshot
                FOREIGN KEY (run_id, snapshot_id)
                REFERENCES world_snapshots (run_id, snapshot_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_snapshot_registrations_ordinal_nonneg
                CHECK (ordinal >= 0),
            CONSTRAINT uq_snapshot_registrations_agent
                UNIQUE (run_id, snapshot_id, agent_id),
            CONSTRAINT uq_snapshot_registrations_entity
                UNIQUE (run_id, snapshot_id, entity_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE snapshot_bodies (
            run_id VARCHAR(128) NOT NULL,
            snapshot_id VARCHAR(128) NOT NULL,
            entity_id VARCHAR(128) NOT NULL,
            location_id VARCHAR(128) NOT NULL,
            health NUMERIC NOT NULL,
            hunger NUMERIC NOT NULL,
            thirst NUMERIC NOT NULL,
            fatigue NUMERIC NOT NULL,
            temperature NUMERIC NOT NULL,
            life_status TEXT NOT NULL,
            CONSTRAINT pk_snapshot_bodies
                PRIMARY KEY (run_id, snapshot_id, entity_id),
            CONSTRAINT fk_snapshot_bodies_snapshot
                FOREIGN KEY (run_id, snapshot_id)
                REFERENCES world_snapshots (run_id, snapshot_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_snapshot_bodies_life_status_closed
                CHECK (life_status IN ('alive', 'dead'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_snapshot_bodies_location
            ON snapshot_bodies (run_id, snapshot_id, location_id)
        """
    )
    op.execute(
        """
        CREATE TABLE snapshot_inventory (
            run_id VARCHAR(128) NOT NULL,
            snapshot_id VARCHAR(128) NOT NULL,
            body_id VARCHAR(128) NOT NULL,
            position INTEGER NOT NULL,
            item_id VARCHAR(128) NOT NULL,
            CONSTRAINT pk_snapshot_inventory
                PRIMARY KEY (run_id, snapshot_id, body_id, position),
            CONSTRAINT fk_snapshot_inventory_body
                FOREIGN KEY (run_id, snapshot_id, body_id)
                REFERENCES snapshot_bodies (run_id, snapshot_id, entity_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_snapshot_inventory_position_nonneg CHECK (position >= 0),
            CONSTRAINT uq_snapshot_inventory_item
                UNIQUE (run_id, snapshot_id, item_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE snapshot_items (
            run_id VARCHAR(128) NOT NULL,
            snapshot_id VARCHAR(128) NOT NULL,
            entity_id VARCHAR(128) NOT NULL,
            name TEXT NOT NULL,
            location_id VARCHAR(128),
            holder_id VARCHAR(128),
            CONSTRAINT pk_snapshot_items
                PRIMARY KEY (run_id, snapshot_id, entity_id),
            CONSTRAINT fk_snapshot_items_snapshot
                FOREIGN KEY (run_id, snapshot_id)
                REFERENCES world_snapshots (run_id, snapshot_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_snapshot_items_one_placement
                CHECK ((location_id IS NULL) <> (holder_id IS NULL)),
            CONSTRAINT ck_snapshot_items_name_nonempty CHECK (char_length(name) > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_snapshot_items_location
            ON snapshot_items (run_id, snapshot_id, location_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_snapshot_items_holder
            ON snapshot_items (run_id, snapshot_id, holder_id)
        """
    )
    op.execute(
        """
        CREATE TABLE snapshot_resources (
            run_id VARCHAR(128) NOT NULL,
            snapshot_id VARCHAR(128) NOT NULL,
            entity_id VARCHAR(128) NOT NULL,
            name TEXT NOT NULL,
            location_id VARCHAR(128) NOT NULL,
            quantity NUMERIC NOT NULL,
            unit TEXT NOT NULL,
            CONSTRAINT pk_snapshot_resources
                PRIMARY KEY (run_id, snapshot_id, entity_id),
            CONSTRAINT fk_snapshot_resources_snapshot
                FOREIGN KEY (run_id, snapshot_id)
                REFERENCES world_snapshots (run_id, snapshot_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_snapshot_resources_quantity_nonneg CHECK (quantity >= 0),
            CONSTRAINT ck_snapshot_resources_quantity_not_nan
                CHECK (quantity::text <> 'NaN'),
            CONSTRAINT ck_snapshot_resources_quantity_not_inf
                CHECK (
                    quantity::float8 != 'Infinity'::float8
                    AND quantity::float8 != '-Infinity'::float8
                ),
            CONSTRAINT ck_snapshot_resources_name_nonempty
                CHECK (char_length(name) > 0),
            CONSTRAINT ck_snapshot_resources_unit_nonempty
                CHECK (char_length(unit) > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_snapshot_resources_location
            ON snapshot_resources (run_id, snapshot_id, location_id)
        """
    )
    op.execute(
        """
        CREATE TABLE snapshot_weather (
            run_id VARCHAR(128) NOT NULL,
            snapshot_id VARCHAR(128) NOT NULL,
            location_id VARCHAR(128) NOT NULL,
            condition TEXT NOT NULL,
            temperature NUMERIC NOT NULL,
            CONSTRAINT pk_snapshot_weather
                PRIMARY KEY (run_id, snapshot_id, location_id),
            CONSTRAINT fk_snapshot_weather_snapshot
                FOREIGN KEY (run_id, snapshot_id)
                REFERENCES world_snapshots (run_id, snapshot_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_snapshot_weather_condition_nonempty
                CHECK (char_length(condition) > 0),
            CONSTRAINT ck_snapshot_weather_temperature_finite
                CHECK (
                    temperature::text <> 'NaN'
                    AND temperature::float8 != 'Infinity'::float8
                    AND temperature::float8 != '-Infinity'::float8
                )
        )
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_history_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'append-only table % rejects %',
                TG_TABLE_NAME,
                TG_OP
                USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$
        """
    )
    for table in _AUTHORITATIVE_TABLES:
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


def downgrade() -> None:
    for table in reversed(_AUTHORITATIVE_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS reject_history_mutation()")
