"""The Stories view's rollups: which sentences each scenario covers, and the
per-story tallies the Stories tab and the JSON `coverage` section read.
"""

from dataclasses import dataclass, field
from typing import TypedDict

from ..model import (
    Clause,
    ClauseTermRef,
    NodeId,
    ReportData,
    Scenario,
    SentenceId,
    StoryId,
)
from .coverage import CoverageMap, build_coverage_map, is_coverage_eligible

type SentenceKey = str
"""`'<story id>:<sentence id>'` — a sentence's handle outside its own story.

Sentence ids are per-story ints, so the story id has to travel with them
wherever sentences from different stories can meet: the report's sentence
filter, and the URL fragment that carries it.
"""


def sentence_key(story_id: StoryId, sentence_id: SentenceId) -> SentenceKey:
    return f'{story_id}:{sentence_id}'


@dataclass
class SentenceCoverage:
    """Per-sentence coverage rollup: which scenarios cover it, pass/skip counts,
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
        """Whether the report can say nothing about this sentence.

        Ineligibility alone no longer settles it: a pin covers an
        under-anchored sentence that narration matching cannot reach, and a
        covered sentence must never render as untracked.
        """
        return not self.eligible and not self.total

    @property
    def failed(self) -> int:
        return self.total - self.passed - self.skipped


@dataclass
class StoryRollup:
    """Per-story precomputed view data: scenarios bound to the story plus a
    per-sentence coverage breakdown. The Stories view consumes both."""

    scenarios: list[Scenario] = field(default_factory=list)
    per_sentence: dict[SentenceId, SentenceCoverage] = field(default_factory=dict)


def build_story_rollups(
    report: ReportData, coverage_maps: CoverageMap
) -> dict[StoryId, StoryRollup]:
    """Per-story view-data: bound scenarios + per-sentence coverage rollup."""
    scenarios_by_story: dict[StoryId, list[Scenario]] = {}
    for scn in report.scenarios:
        for story_id in scn.story_ids:
            scenarios_by_story.setdefault(story_id, []).append(scn)

    rollups: dict[StoryId, StoryRollup] = {}
    for story in report.stories:
        scenarios = scenarios_by_story.get(story.id, [])
        per_sentence: dict[SentenceId, SentenceCoverage] = {}
        for sentence in story.sentences:
            covered_by: list[NodeId] = []
            passed = 0
            skipped = 0
            for scn in scenarios:
                if sentence.id not in coverage_maps[scn.id].get(story.id, set()):
                    continue
                covered_by.append(scn.id)
                if scn.status == 'passed':
                    passed += 1
                elif scn.status == 'skipped':
                    skipped += 1
            per_sentence[sentence.id] = SentenceCoverage(
                scenario_ids=covered_by,
                passed=passed,
                skipped=skipped,
                eligible=is_coverage_eligible(sentence),
            )
        rollups[story.id] = StoryRollup(scenarios=scenarios, per_sentence=per_sentence)
    return rollups


class CoverageRecord(TypedDict):
    """One sentence's coverage as the JSON report carries it, under the
    top-level `coverage` key — in story then sentence order."""

    story_id: StoryId
    sentence_id: SentenceId
    tracked: bool
    scenario_ids: list[NodeId]


def build_coverage_records(report: ReportData) -> list[CoverageRecord]:
    """Built from the rollups the Stories tab renders, so the JSON and the
    HTML cannot disagree on what is covered."""
    rollups = build_story_rollups(report, build_coverage_map(report))
    return [
        CoverageRecord(
            story_id=story_id,
            sentence_id=sentence_id,
            tracked=not coverage.untracked,
            scenario_ids=coverage.scenario_ids,
        )
        for story_id, rollup in rollups.items()
        for sentence_id, coverage in rollup.per_sentence.items()
    ]


def build_scenario_sentence_index(
    coverage_maps: CoverageMap,
) -> dict[NodeId, dict[StoryId, list[SentenceId]]]:
    return {
        scn_id: {story_id: sorted(covered) for story_id, covered in per_story.items()}
        for scn_id, per_story in coverage_maps.items()
    }


def build_sentence_labels(report: ReportData) -> dict[SentenceKey, str]:
    """For each sentence, its prose as plain text, keyed by `SentenceKey`.

    Lets the report name a sentence outside the story timeline — in the
    Scenarios view's sentence filter chip — where the numbered bubble that
    identifies it in the timeline carries no meaning on its own.
    """
    return {
        sentence_key(story.id, sentence.id): ' · '.join(
            _clause_text(clause) for clause in sentence.clauses
        )
        for story in report.stories
        for sentence in story.sentences
    }


def _clause_text(clause: Clause) -> str:
    """One clause as plain prose. Term refs read as their surface form,
    the same word the timeline shows in a pill."""
    return ' '.join(
        part.display if isinstance(part, ClauseTermRef) else part.text
        for part in clause.parts
    )
