from importlib.resources.abc import Traversable

import pytest

from pytest_given.cli.skills import BUNDLED_SKILLS_ROOT


def _skill_dirs() -> list[Traversable]:
    return [child for child in BUNDLED_SKILLS_ROOT.iterdir() if child.is_dir()]


def _frontmatter(skill_md: Traversable) -> dict[str, str]:
    text = skill_md.read_text(encoding='utf-8')
    assert text.startswith('---\n')
    block = text.split('---\n')[1]
    assert len(block) <= 1024
    fields = {}
    for line in block.strip().splitlines():
        key, _, value = line.partition(':')
        fields[key.strip()] = value.strip()
    return fields


BUNDLED_SKILLS = [
    'pytest-given-authoring',
    'pytest-given-navigating',
    'pytest-given-reviewing',
]


def test_bundles_the_expected_skills() -> None:
    assert sorted(d.name for d in _skill_dirs()) == BUNDLED_SKILLS


@pytest.mark.parametrize('skill', BUNDLED_SKILLS)
def test_every_skill_has_a_skill_md(skill: str) -> None:
    assert (BUNDLED_SKILLS_ROOT / skill / 'SKILL.md').is_file()


@pytest.mark.parametrize('skill', BUNDLED_SKILLS)
def test_reference_guides_are_bundled(skill: str) -> None:
    assert (BUNDLED_SKILLS_ROOT / skill / 'references').is_dir()


def test_reviewing_skill_cross_reference_target_exists() -> None:
    """The reviewing skill links ../pytest-given-authoring/references/scenarios.md."""
    root = BUNDLED_SKILLS_ROOT / 'pytest-given-authoring'
    assert (root / 'references' / 'scenarios.md').is_file()


def test_reviewing_skill_story_coverage_reference_is_bundled() -> None:
    """The reviewing skill links references/story-coverage.md for the JSON query."""
    root = BUNDLED_SKILLS_ROOT / 'pytest-given-reviewing'
    assert (root / 'references' / 'story-coverage.md').is_file()


def test_reviewing_skill_pairs_reference_is_bundled() -> None:
    """The reviewing skill links references/pairs.md for the narration/body dump."""
    root = BUNDLED_SKILLS_ROOT / 'pytest-given-reviewing'
    assert (root / 'references' / 'pairs.md').is_file()


def test_skill_frontmatter_names_match_directories() -> None:
    for skill_dir in _skill_dirs():
        fields = _frontmatter(skill_dir / 'SKILL.md')
        assert fields['name'] == skill_dir.name
        assert fields['description'].startswith('Use when')
