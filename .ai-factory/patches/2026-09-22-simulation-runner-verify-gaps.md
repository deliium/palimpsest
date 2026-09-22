# Patch: simulation-runner verify gaps

**Date:** 2026-09-22
**Tags:** serialization, runner, experiments, persistence, verify

## Root Cause

1. `DeclaredTransmission.root_communication_id` was encoded into canonical JSON but omitted from `_require_keys` allowed fields, so every communication round-trip raised `invalid_fields`.
2. Durable runner construction always raised `DURABLE_UNSUPPORTED`; Alembic `0009` ORM existed without ports/adapters or runner wiring.
3. Experiment collectors were summary-only; plan-listed integration modules were missing.

## Fix

- Allow optional `root_communication_id` on decode while retaining legacy fallback when absent.
- Added pending-finalization / attempt-state ports, in-memory + SQLAlchemy adapters, and durable `PersistentSimulationService` authority path when repositories are injected.
- Expanded A-E collectors, coordinator metric attachment, and network-free integration proofs.

## Prevention

- When adding a serialized field, update `_require_keys` required/optional sets in the same change and keep a round-trip unit test green.
- Durable features need ports + adapters + a construction path that fails closed without injected repositories rather than a hard permanent reject.
