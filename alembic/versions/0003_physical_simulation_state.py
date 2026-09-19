"""Physical simulation state columns and legacy backfill.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-19

Adds normalized physical fields (topology, capacities, item/resource kinds,
carry capacity, weather condition-only) and run-level physical rules columns.
Legacy rows receive explicit defaults; weather temperature is dropped because
ambient temperature is derived at observation time.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- simulation_runs physical rules ---
    op.execute(
        """
        ALTER TABLE simulation_runs
            ADD COLUMN physical_rules_version TEXT,
            ADD COLUMN physical_rules_fingerprint VARCHAR(64),
            ADD COLUMN physical_rules_canonical JSONB
        """
    )
    op.execute(
        """
        ALTER TABLE simulation_runs
            ADD CONSTRAINT ck_simulation_runs_rules_fingerprint_hex
            CHECK (
                physical_rules_fingerprint IS NULL
                OR (
                    char_length(physical_rules_fingerprint) = 64
                    AND physical_rules_fingerprint ~ '^[0-9a-f]{64}$'
                )
            )
        """
    )
    op.execute(
        """
        ALTER TABLE simulation_runs
            ADD CONSTRAINT ck_simulation_runs_rules_pair
            CHECK (
                (physical_rules_version IS NULL)
                = (physical_rules_fingerprint IS NULL)
                AND (physical_rules_version IS NULL)
                = (physical_rules_canonical IS NULL)
            )
        """
    )

    # --- snapshot_locations physical environment ---
    op.execute(
        """
        ALTER TABLE snapshot_locations
            ADD COLUMN adjacent JSONB,
            ADD COLUMN body_capacity INTEGER,
            ADD COLUMN item_capacity INTEGER,
            ADD COLUMN base_temperature NUMERIC,
            ADD COLUMN shelter_factor NUMERIC,
            ADD COLUMN visibility_factor NUMERIC
        """
    )
    op.execute(
        """
        UPDATE snapshot_locations
        SET adjacent = '[]'::jsonb,
            body_capacity = 4,
            item_capacity = 8,
            base_temperature = 20.0,
            shelter_factor = 0.0,
            visibility_factor = 1.0
        WHERE adjacent IS NULL
        """
    )
    op.execute(
        """
        ALTER TABLE snapshot_locations
            ALTER COLUMN adjacent SET NOT NULL,
            ALTER COLUMN body_capacity SET NOT NULL,
            ALTER COLUMN item_capacity SET NOT NULL,
            ALTER COLUMN base_temperature SET NOT NULL,
            ALTER COLUMN shelter_factor SET NOT NULL,
            ALTER COLUMN visibility_factor SET NOT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE snapshot_locations
            ADD CONSTRAINT ck_snapshot_locations_body_capacity_positive
                CHECK (body_capacity >= 1),
            ADD CONSTRAINT ck_snapshot_locations_item_capacity_nonneg
                CHECK (item_capacity >= 0),
            ADD CONSTRAINT ck_snapshot_locations_shelter_unit
                CHECK (shelter_factor >= 0 AND shelter_factor <= 1),
            ADD CONSTRAINT ck_snapshot_locations_visibility_unit
                CHECK (visibility_factor >= 0 AND visibility_factor <= 1)
        """
    )

    # --- snapshot_bodies carry capacity ---
    op.execute(
        "ALTER TABLE snapshot_bodies ADD COLUMN carry_capacity INTEGER"
    )
    op.execute(
        """
        UPDATE snapshot_bodies
        SET carry_capacity = 10
        WHERE carry_capacity IS NULL
        """
    )
    op.execute(
        """
        ALTER TABLE snapshot_bodies
            ALTER COLUMN carry_capacity SET NOT NULL,
            ADD CONSTRAINT ck_snapshot_bodies_carry_capacity_positive
                CHECK (carry_capacity >= 1)
        """
    )

    # --- snapshot_items kind/load ---
    op.execute(
        """
        ALTER TABLE snapshot_items
            ADD COLUMN kind TEXT,
            ADD COLUMN load INTEGER
        """
    )
    op.execute(
        """
        UPDATE snapshot_items
        SET kind = 'generic',
            load = 1
        WHERE kind IS NULL
        """
    )
    op.execute(
        """
        ALTER TABLE snapshot_items
            ALTER COLUMN kind SET NOT NULL,
            ALTER COLUMN load SET NOT NULL,
            ADD CONSTRAINT ck_snapshot_items_kind_nonempty
                CHECK (char_length(kind) > 0),
            ADD CONSTRAINT ck_snapshot_items_load_positive
                CHECK (load >= 1)
        """
    )

    # --- snapshot_resources kind/max/regen ---
    op.execute(
        """
        ALTER TABLE snapshot_resources
            ADD COLUMN kind TEXT,
            ADD COLUMN maximum_quantity NUMERIC,
            ADD COLUMN regeneration_per_tick NUMERIC
        """
    )
    op.execute(
        """
        UPDATE snapshot_resources
        SET kind = 'material',
            maximum_quantity = quantity,
            regeneration_per_tick = 0.0
        WHERE kind IS NULL
        """
    )
    op.execute(
        """
        ALTER TABLE snapshot_resources
            ALTER COLUMN kind SET NOT NULL,
            ALTER COLUMN maximum_quantity SET NOT NULL,
            ALTER COLUMN regeneration_per_tick SET NOT NULL,
            ADD CONSTRAINT ck_snapshot_resources_kind_nonempty
                CHECK (char_length(kind) > 0),
            ADD CONSTRAINT ck_snapshot_resources_maximum_quantity_nonneg
                CHECK (maximum_quantity >= 0),
            ADD CONSTRAINT ck_snapshot_resources_quantity_within_maximum
                CHECK (quantity <= maximum_quantity),
            ADD CONSTRAINT ck_snapshot_resources_regeneration_nonneg
                CHECK (regeneration_per_tick >= 0)
        """
    )

    # --- snapshot_weather condition-only ---
    op.execute(
        """
        ALTER TABLE snapshot_weather
            DROP CONSTRAINT IF EXISTS ck_snapshot_weather_temperature_finite
        """
    )
    op.execute("ALTER TABLE snapshot_weather DROP COLUMN temperature")


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE snapshot_weather
            ADD COLUMN temperature NUMERIC
        """
    )
    op.execute(
        """
        UPDATE snapshot_weather SET temperature = 20.0 WHERE temperature IS NULL
        """
    )
    op.execute(
        """
        ALTER TABLE snapshot_weather
            ALTER COLUMN temperature SET NOT NULL,
            ADD CONSTRAINT ck_snapshot_weather_temperature_finite
                CHECK (
                    temperature::text <> 'NaN'
                    AND temperature::float8 != 'Infinity'::float8
                    AND temperature::float8 != '-Infinity'::float8
                )
        """
    )

    op.execute(
        """
        ALTER TABLE snapshot_resources
            DROP CONSTRAINT IF EXISTS ck_snapshot_resources_regeneration_nonneg,
            DROP CONSTRAINT IF EXISTS ck_snapshot_resources_quantity_within_maximum,
            DROP CONSTRAINT IF EXISTS ck_snapshot_resources_maximum_quantity_nonneg,
            DROP CONSTRAINT IF EXISTS ck_snapshot_resources_kind_nonempty,
            DROP COLUMN kind,
            DROP COLUMN maximum_quantity,
            DROP COLUMN regeneration_per_tick
        """
    )
    op.execute(
        """
        ALTER TABLE snapshot_items
            DROP CONSTRAINT IF EXISTS ck_snapshot_items_load_positive,
            DROP CONSTRAINT IF EXISTS ck_snapshot_items_kind_nonempty,
            DROP COLUMN kind,
            DROP COLUMN load
        """
    )
    op.execute(
        """
        ALTER TABLE snapshot_bodies
            DROP CONSTRAINT IF EXISTS ck_snapshot_bodies_carry_capacity_positive,
            DROP COLUMN carry_capacity
        """
    )
    op.execute(
        """
        ALTER TABLE snapshot_locations
            DROP CONSTRAINT IF EXISTS ck_snapshot_locations_visibility_unit,
            DROP CONSTRAINT IF EXISTS ck_snapshot_locations_shelter_unit,
            DROP CONSTRAINT IF EXISTS ck_snapshot_locations_item_capacity_nonneg,
            DROP CONSTRAINT IF EXISTS ck_snapshot_locations_body_capacity_positive,
            DROP COLUMN adjacent,
            DROP COLUMN body_capacity,
            DROP COLUMN item_capacity,
            DROP COLUMN base_temperature,
            DROP COLUMN shelter_factor,
            DROP COLUMN visibility_factor
        """
    )
    op.execute(
        """
        ALTER TABLE simulation_runs
            DROP CONSTRAINT IF EXISTS ck_simulation_runs_rules_pair,
            DROP CONSTRAINT IF EXISTS ck_simulation_runs_rules_fingerprint_hex,
            DROP COLUMN physical_rules_version,
            DROP COLUMN physical_rules_fingerprint,
            DROP COLUMN physical_rules_canonical
        """
    )
