"""Office belief threading through runtime outcomes and disabled passthrough."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V49,
    RUNNER_SCHEMA_VERSION_V50,
    InstitutionConceptMode,
    OfficeSuccessionMode,
)


def _config(*, office: bool, max_ticks: int = 4):
    definition = institutionalization_scenario(seed=23, max_ticks=max_ticks)
    base = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bf-institution-on"
    )
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                institution_concept_mode=InstitutionConceptMode.DISABLED,
                office_succession_mode=(
                    OfficeSuccessionMode.DETERMINISTIC
                    if office
                    else OfficeSuccessionMode.DISABLED
                ),
            ),
        )
        for agent in base.agents
    )
    if not office:
        return replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V49,
            agents=tuple(
                replace(
                    agent,
                    cognition=replace(
                        agent.cognition,
                        institution_concept_mode=InstitutionConceptMode.DETERMINISTIC,
                    ),
                )
                for agent in agents
            ),
        )
    return replace(base, schema_version=RUNNER_SCHEMA_VERSION_V50, agents=agents)


@pytest.mark.asyncio
async def test_enabled_owners_export_one_empty_ledger_each() -> None:
    config = _config(office=True)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-office-runtime")
    ) as runner:
        result = await runner.run()
    owners = [agent.agent_id.value for agent in config.agents]
    assert [ledger.owner_id.value for ledger in result.office_concept_ledgers] == owners
    assert all(
        concept.status.value == "proposed"
        for ledger in result.office_concept_ledgers
        for concept in ledger.concepts
    )


@pytest.mark.asyncio
async def test_disabled_owners_export_no_ledger() -> None:
    config = _config(office=False)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-office-disabled")
    ) as runner:
        result = await runner.run()
    assert result.office_concept_ledgers == ()


@pytest.mark.asyncio
async def test_runtime_is_deterministic_for_office_mode() -> None:
    config = _config(office=True)
    first = None
    second = None
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-office-det")
    ) as runner:
        first = await runner.run()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-office-det")
    ) as runner:
        second = await runner.run()
    assert first.office_concept_ledgers == second.office_concept_ledgers
    assert first.stop_reason == second.stop_reason


def test_office_direction_preference_requires_recognition() -> None:
    from agents.cognition.models import ActionDirection
    from agents.cognition.offices import (
        OfficeConcept,
        OfficeConceptLedger,
        OfficeConceptStatus,
        OfficeDutyBelief,
        OfficeDutyKind,
        OfficeFunction,
        office_concept_id,
        office_direction_preference,
        office_inception_digest,
        office_role_signature,
    )
    from agents.models import AgentId

    owner = AgentId("ada")
    context = "a" * 16
    inception = office_inception_digest(OfficeFunction.HELP, context, "inception")
    office_id = office_concept_id(owner, inception)
    duty = OfficeDutyBelief(
        duty_id="d" * 64,
        kind=OfficeDutyKind.PERFORM,
        function=OfficeFunction.HELP,
        context_key=context,
        strength=0.6,
        first_tick=1,
        last_tick=2,
    )

    def concept(status: OfficeConceptStatus) -> OfficeConcept:
        return OfficeConcept(
            office_id=office_id,
            owner_id=owner,
            function=OfficeFunction.HELP,
            context_key=context,
            inception_digest=inception,
            collision_discriminator=0,
            role_signature=office_role_signature(
                OfficeFunction.HELP, context, (OfficeDutyKind.PERFORM,)
            ),
            status=status,
            function_strength=0.6,
            expectation_strength=0.5,
            endorsement_strength=0.4,
            first_tick=1,
            last_tick=2,
            evidence_count=3,
            independent_root_count=2,
            duties=(duty,),
        )

    recognized = OfficeConceptLedger(
        owner_id=owner, concepts=(concept(OfficeConceptStatus.RECOGNIZED),)
    )
    proposed = OfficeConceptLedger(
        owner_id=owner, concepts=(concept(OfficeConceptStatus.PROPOSED),)
    )
    assert office_direction_preference(recognized) is ActionDirection.HELP
    assert office_direction_preference(proposed) is None
    assert office_direction_preference(None) is None
