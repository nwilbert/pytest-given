"""What a scenario is paired and suggested by."""

from ..model import Scenario, node_base


def scenario_identity(scenario: Scenario) -> str:
    return node_base(scenario.id) if scenario.parameters is not None else scenario.id
