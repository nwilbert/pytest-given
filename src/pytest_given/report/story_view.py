"""The Stories view's rollups: which activities each scenario covers, and the
per-story tallies the template reads.
"""

from dataclasses import dataclass, field

from ..model import (
    ActivityId,
    ActivityPath,
    ActivityTermRef,
    NodeId,
    ReportData,
    Scenario,
    StoryId,
)
from .coverage import CoverageMap, is_coverage_eligible

type ActivityKey = str
"""`'<story id>:<activity id>'` — an activity's handle outside its own story.

Activity ids are per-story ints, so the story id has to travel with them
wherever activities from different stories can meet: the report's activity
filter, and the URL fragment that carries it.
"""


def activity_key(story_id: StoryId, activity_id: ActivityId) -> ActivityKey:
    return f'{story_id}:{activity_id}'


@dataclass
class ActivityCoverage:
    """Per-activity coverage rollup: which scenarios cover it, pass/skip counts,
    total, and whether it is eligible for narration matching at all."""

    scenario_ids: list[NodeId] = field(default_factory=list)
    passed: int = 0
    skipped: int = 0
    eligible: bool = True

    @property
    def total(self) -> int:
        return len(self.scenario_ids)

    @property
    def untracked(self) -> bool:
        """Whether the report can say nothing about this activity.

        Ineligibility alone no longer settles it: an `activity=` pin covers an
        under-anchored activity that narration matching cannot reach, and a
        covered activity must never render as untracked.
        """
        return not self.eligible and not self.total

    @property
    def failed(self) -> int:
        return self.total - self.passed - self.skipped


@dataclass
class StoryRollup:
    """Per-story precomputed view data: scenarios bound to the story plus a
    per-activity coverage breakdown. The Stories view consumes both."""

    scenarios: list[Scenario] = field(default_factory=list)
    per_activity: dict[ActivityId, ActivityCoverage] = field(default_factory=dict)


def build_story_rollups(
    report: ReportData, coverage_maps: CoverageMap
) -> dict[StoryId, StoryRollup]:
    """Per-story view-data: bound scenarios + per-activity coverage rollup."""
    scenarios_by_story: dict[StoryId, list[Scenario]] = {}
    for scn in report.scenarios:
        if scn.story_id is None:
            continue
        scenarios_by_story.setdefault(scn.story_id, []).append(scn)

    rollups: dict[StoryId, StoryRollup] = {}
    for story in report.stories:
        scenarios = scenarios_by_story.get(story.id, [])
        per_activity: dict[ActivityId, ActivityCoverage] = {}
        for activity in story.activities:
            covered_by: list[NodeId] = []
            passed = 0
            skipped = 0
            for scn in scenarios:
                if activity.id not in coverage_maps[scn.id]:
                    continue
                covered_by.append(scn.id)
                if scn.status == 'passed':
                    passed += 1
                elif scn.status == 'skipped':
                    skipped += 1
            per_activity[activity.id] = ActivityCoverage(
                scenario_ids=covered_by,
                passed=passed,
                skipped=skipped,
                eligible=is_coverage_eligible(activity),
            )
        rollups[story.id] = StoryRollup(scenarios=scenarios, per_activity=per_activity)
    return rollups


def build_scenario_activity_index(
    coverage_maps: CoverageMap,
) -> dict[NodeId, list[ActivityId]]:
    return {scn_id: sorted(covered) for scn_id, covered in coverage_maps.items()}


def build_activity_labels(report: ReportData) -> dict[ActivityKey, str]:
    """For each activity, its prose as plain text, keyed by `ActivityKey`.

    Lets the report name an activity outside the story timeline — in the
    Scenarios view's activity filter chip — where the numbered bubble that
    identifies it in the timeline carries no meaning on its own.
    """
    return {
        activity_key(story.id, activity.id): ' · '.join(
            _path_text(path) for path in activity.paths
        )
        for story in report.stories
        for activity in story.activities
    }


def _path_text(path: ActivityPath) -> str:
    """One activity path as plain prose. Term refs read as their surface form,
    the same word the timeline shows in a pill."""
    return ' '.join(
        part.display if isinstance(part, ActivityTermRef) else part.text
        for part in path.parts
    )
