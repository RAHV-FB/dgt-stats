"""The findings document is generated from the committed tables and matches the committed file."""

import re

from dgt_stats import findings

SECTIONS = 10


def test_the_committed_document_is_the_build() -> None:
    assert findings.DOCUMENT.read_text(encoding="utf-8") == findings.render()


def test_the_document_has_every_section_with_strength_and_limit() -> None:
    text = findings.render()
    headings = re.findall(r"^## (\d+)\. ", text, flags=re.M)
    assert headings == [str(number) for number in range(1, SECTIONS + 1)]
    assert text.count("Main limit:") == SECTIONS
    for section in re.split(r"^## ", text, flags=re.M)[1:]:
        assert re.search(r"\*\*(Strong|Moderate|Weak|Not established)\.\*\*", section)


def test_the_document_is_short_plain_markdown() -> None:
    text = findings.render()
    assert 120 <= len(text.splitlines()) <= 200
    assert text.startswith("# Findings\n")
    assert "<" not in text and "TODO" not in text
    assert all(len(line) <= 100 for line in text.splitlines() if not line.startswith("#"))


def test_the_document_is_deterministic() -> None:
    assert findings.render() == findings.render()
