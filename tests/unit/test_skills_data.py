from importlib.resources import files
from importlib.resources.abc import Traversable

import pytest


def _skill_dirs() -> list[Traversable]:
    root = files('pytest_given') / 'skills_data'
    return [child for child in root.iterdir() if child.is_dir()]


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


BUNDLED_SKILLS = ['pytest-given-authoring', 'pytest-given-navigating']


def test_bundles_the_expected_skills() -> None:
    assert sorted(d.name for d in _skill_dirs()) == BUNDLED_SKILLS


@pytest.mark.parametrize('skill', BUNDLED_SKILLS)
@pytest.mark.parametrize('required', ['SKILL.md', 'references'])
def test_skill_layout(skill: str, required: str) -> None:
    root = files('pytest_given') / 'skills_data' / skill
    assert (root / required).is_dir() or (root / required).is_file()


def test_skill_frontmatter_names_match_directories() -> None:
    for skill_dir in _skill_dirs():
        fields = _frontmatter(skill_dir / 'SKILL.md')
        assert fields['name'] == skill_dir.name
        assert fields['description'].startswith('Use when')
