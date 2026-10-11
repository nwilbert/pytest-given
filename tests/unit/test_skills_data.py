import re
from importlib.resources.abc import Traversable
from pathlib import Path, PurePosixPath

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
    'pytest-given-citing',
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


@pytest.mark.parametrize('skill', BUNDLED_SKILLS)
def test_skill_md_says_the_installed_copy_is_overwritten(skill: str) -> None:
    text = (BUNDLED_SKILLS_ROOT / skill / 'SKILL.md').read_text(encoding='utf-8')
    assert 'overwritten on reinstall' in text


def test_every_relative_link_resolves_to_a_bundled_file_and_heading() -> None:
    broken = [
        f'{document}: {link}'
        for document in _markdown_documents()
        for link in _relative_links(_read(document))
        if not _resolves(document, link)
    ]
    assert broken == []


_CODE = re.compile(r'```.*?```|`[^`\n]*`', re.DOTALL)
_LINK = re.compile(r'\[[^\]]*\]\(([^)\s]+)\)')
_HEADING = re.compile(r'^#+ (.+)$', re.MULTILINE)


def _markdown_documents() -> list[PurePosixPath]:
    return [
        PurePosixPath(skill, *path.relative_to(skill_root).parts)
        for skill in BUNDLED_SKILLS
        for skill_root in [Path(str(BUNDLED_SKILLS_ROOT / skill))]
        for path in sorted(skill_root.rglob('*.md'))
    ]


def _read(document: PurePosixPath) -> str:
    return BUNDLED_SKILLS_ROOT.joinpath(*document.parts).read_text(encoding='utf-8')


def _relative_links(text: str) -> list[str]:
    return [
        link
        for link in _LINK.findall(_CODE.sub('', text))
        if '://' not in link and not link.startswith('mailto:')
    ]


def _resolves(document: PurePosixPath, link: str) -> bool:
    target, _, anchor = link.partition('#')
    parts: list[str] = list(document.parent.parts)
    for part in PurePosixPath(target).parts if target else ():
        if part == '..':
            parts.pop()
        else:
            parts.append(part)
    resolved = PurePosixPath(*parts) if target else document
    if not BUNDLED_SKILLS_ROOT.joinpath(*resolved.parts).is_file():
        return False
    return not anchor or anchor in _heading_slugs(_read(resolved))


def _heading_slugs(text: str) -> set[str]:
    return {
        re.sub(r'[^\w\- ]', '', heading.strip().lower()).replace(' ', '-')
        for heading in _HEADING.findall(_CODE.sub('', text))
    }


def test_skill_frontmatter_names_match_directories() -> None:
    for skill_dir in _skill_dirs():
        fields = _frontmatter(skill_dir / 'SKILL.md')
        assert fields['name'] == skill_dir.name
        assert fields['description'].startswith('Use when')
