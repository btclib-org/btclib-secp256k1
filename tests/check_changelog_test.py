# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for the `CHANGELOG.md` open-section check of `.github/scripts`.

The script's own module docstring is the argument for what it checks and
why; this exercises both readings of it.
`test_this_trees_own_open_section_is_clean` runs it unmodified, against
this tree's own file, which is the same question the `pre-commit` hook
asks on every commit. Every other test builds a small file of its own
instead, one for each of the five checks and the shapes each must not
answer to. `[tool.coverage.run]` measures the script by path, so what
this tree's own file never takes is here too -- a file with no release
heading -- and so is the entry-point guard, run as `__main__`.

The script is loaded by path, `.github/scripts` being no package.
"""

from __future__ import annotations

import importlib.util
import runpy
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).parents[1] / ".github" / "scripts" / "check_changelog.py"

_CLEAN = """\
# Changelog

## Unreleased

### First entry

- **first thing** (closes #1): one.

### Second entry

- **second thing** (closes #2): two.
"""


@pytest.fixture
def script(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Return the script, imported by path, registered before it runs."""
    spec = importlib.util.spec_from_file_location("check_changelog", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "check_changelog", module)
    spec.loader.exec_module(module)
    return module


def test_this_trees_own_open_section_is_clean(script: ModuleType) -> None:
    """This repository's own `CHANGELOG.md`, read unmodified, passes."""
    assert script.main() == 0


def test_a_clean_fixture_is_a_positive_control(script: ModuleType) -> None:
    """The fixture text itself passes, which is what its problems() answer."""
    assert script.problems(_CLEAN) == []


def test_a_repeated_heading_is_caught(script: ModuleType) -> None:
    """Two `### ` headings with the same text is the first check."""
    text = _CLEAN.replace("Second entry", "First entry")
    found = script.problems(text)
    assert len(found) == 1
    assert "repeats the heading" in found[0]


def test_two_entries_closing_one_issue_is_caught(script: ModuleType) -> None:
    """Two entries each `(closes #N)` the same number is the second check."""
    text = _CLEAN.replace("(closes #2)", "(closes #1)")
    found = script.problems(text)
    assert len(found) == 1
    assert "closes #1, already closed by" in found[0]


def test_a_heading_glued_to_the_line_above_is_caught(script: ModuleType) -> None:
    """A `### ` with no blank line above it is the third check."""
    text = _CLEAN.replace("\n\n### Second entry", "\n### Second entry")
    found = script.problems(text)
    assert len(found) == 1
    assert "no blank line above it" in found[0]


def test_the_same_entry_closing_twice_is_not_reported(script: ModuleType) -> None:
    """A list body citing the issue its heading answers again is normal.

    Section 9 of the organization standard lets an entry make several
    related claims about the one issue it answers, each bullet citing it
    again.
    """
    text = _CLEAN.replace(
        "- **first thing** (closes #1): one.\n",
        "- **first thing** (closes #1): one.\n\n- **again** (closes #1): still one.\n",
    )
    assert script.problems(text) == []


def test_an_issue_advanced_by_two_entries_is_not_reported(script: ModuleType) -> None:
    """`(issue #N)` recurring across entries is section 9's own shape.

    A long-lived issue is answered across several entries under
    `(issue #N)` -- normal, by section 9's *A live claim* rule, and not
    what the second check asks about.
    """
    text = _CLEAN.replace("(closes #2)", "(issue #1)")
    assert script.problems(text) == []


def test_one_entry_advancing_and_another_closing_is_not_reported(
    script: ModuleType,
) -> None:
    """`(issue #N)` followed later by `(closes #N)` is the ordinary case."""
    text = _CLEAN.replace("(closes #1)", "(issue #1)")
    assert script.problems(text.replace("(closes #2)", "(closes #1)")) == []


def test_a_mixed_group_closes_only_the_keyword_it_names(script: ModuleType) -> None:
    """`(closes #593, issue #571)` closes the first number, not the second."""
    text = _CLEAN.replace("(closes #1)", "(closes #593, issue #571)").replace(
        "(closes #2)",
        "(closes #571)",
    )
    assert script.problems(text) == []


def test_two_entries_closing_the_same_number_under_mixed_groups_is_caught(
    script: ModuleType,
) -> None:
    """The keyword nearest a token decides it, in both entries at once."""
    text = _CLEAN.replace("(closes #1)", "(issue #9, closes #1)").replace(
        "(closes #2)",
        "(closes #1)",
    )
    found = script.problems(text)
    assert len(found) == 1
    assert "closes #1, already closed by" in found[0]


def test_a_cross_repository_citation_compares_as_written(script: ModuleType) -> None:
    """A bare `#N` and a qualified `owner/repo#N` are different tokens."""
    text = _CLEAN.replace("(closes #2)", "(closes btclib-org/btclib-node#1)")
    assert script.problems(text) == []


def test_two_qualified_citations_of_one_issue_are_caught(script: ModuleType) -> None:
    """Two entries closing the same `owner/repo#N` collide as written."""
    text = _CLEAN.replace("(closes #1)", "(closes btclib-org/btclib-node#1)").replace(
        "(closes #2)",
        "(closes btclib-org/btclib-node#1)",
    )
    found = script.problems(text)
    assert len(found) == 1
    assert "btclib-org/btclib-node#1, already closed by" in found[0]


def test_a_released_section_is_outside_the_open_one(script: ModuleType) -> None:
    """A duplicate under a second `## ` is a release, not the open section."""
    text = _CLEAN + "\n## v1.0\n\n### First entry\n\n- **again** (closes #1): one.\n"
    assert script.problems(text) == []


def test_a_quoted_example_is_not_read_as_a_citation(script: ModuleType) -> None:
    """A backtick-quoted `(closes #N)` is prose, not a citation of its own."""
    text = _CLEAN.replace(
        "- **second thing** (closes #2): two.",
        "- **second thing** (closes #2): the first entry's body reads"
        " `(closes #1)` verbatim.",
    )
    assert script.problems(text) == []


def test_a_file_with_no_release_heading_is_one_open_section(
    script: ModuleType,
) -> None:
    """With no `## ` at all the whole file is the open section.

    The section then has no `### ` either, so its one entry is the
    heading-less preamble, and nothing in it is for a check to find.
    """
    text = "# Changelog\n\n- **only thing** (closes #1): one.\n"
    assert script.open_section(text) == (text, 0)
    assert script.problems(text) == []


_LONG = "- one\n- two\n- three\n- four\n"


def test_a_long_body_after_the_rule_entry_is_caught(script: ModuleType) -> None:
    """The fourth check reads from the entry the rule entered with."""
    rule = f"### {script.RULE_HEADING}\n\n- rule.\n"
    found = script.problems(f"{_CLEAN}\n{rule}\n### Long\n\n{_LONG}")
    assert len(found) == 1
    assert "'Long'" in found[0]
    assert "4 lines" in found[0]


def test_a_long_body_before_the_rule_entry_is_not_reported(script: ModuleType) -> None:
    """An entry above the rule entry predates the rule and stays."""
    rule = f"### {script.RULE_HEADING}\n\n- rule.\n"
    assert script.problems(f"{_CLEAN}\n### Long\n\n{_LONG}\n{rule}") == []


def test_misplaced_entries_is_clean_within_the_grandfathered_count(
    script: ModuleType,
) -> None:
    """A count at or below `grandfathered` is not a misplacement."""
    text = f"{_CLEAN}\n### {script.RULE_HEADING}\n\n- rule.\n"
    section, base = script.open_section(text)
    assert script.misplaced_entries(text, section, base, grandfathered=2) == []


def test_misplaced_entries_is_caught_past_the_grandfathered_count(
    script: ModuleType,
) -> None:
    """More entries above `RULE_HEADING` than `grandfathered` is refused.

    This is the blind spot btclib-org/.github#1204 named: an entry
    landed above `RULE_HEADING` by mistake reads, to `long_bodies()`, as
    older than the rule it postdates, and passes unmeasured. This check
    is what refuses it instead.
    """
    text = f"{_CLEAN}\n### {script.RULE_HEADING}\n\n- rule.\n"
    section, base = script.open_section(text)
    found = script.misplaced_entries(text, section, base, grandfathered=1)
    assert len(found) == 1
    assert "2 entries land above the rule heading" in found[0]
    assert "more than the 1 this repository grandfathers" in found[0]


def test_misplaced_entries_is_silent_where_the_rule_heading_is_absent(
    script: ModuleType,
) -> None:
    """A released section has no `RULE_HEADING` to count entries above."""
    section, base = script.open_section(_CLEAN)
    assert script.misplaced_entries(_CLEAN, section, base, grandfathered=0) == []


def test_a_misplaced_long_body_is_refused_once_grandfathered_is_exceeded(
    script: ModuleType,
) -> None:
    """The demonstrated shape: a misplaced, over-long entry is refused.

    `test_a_long_body_before_the_rule_entry_is_not_reported` above shows
    `long_bodies()` alone never measures this entry; `misplaced_entries()`
    wired into `problems()`, with the count already past what predates
    the rule, is what stops it landing silently.
    """
    rule = f"### {script.RULE_HEADING}\n\n- rule.\n"
    text = f"{_CLEAN}\n### Long\n\n{_LONG}\n{rule}"
    section, base = script.open_section(text)
    found = script.misplaced_entries(text, section, base, grandfathered=2)
    assert len(found) == 1
    assert "an entry has landed above it" in found[0]


def test_misplaced_entries_uses_the_repository_constant_when_none_is_passed(
    script: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`problems()`'s own call takes no override, so this is what it reads.

    `test_misplaced_entries_is_caught_past_the_grandfathered_count` above
    exercises the override a test uses instead; this is the path
    `misplaced_entries()` takes on a real `CHANGELOG.md`, reading
    `_GRANDFATHERED_ENTRIES` from this repository's own trailing section
    rather than a fixture the size of the entries that constant actually
    names.
    """
    rule = f"### {script.RULE_HEADING}\n\n- rule.\n"
    text = f"{_CLEAN}\n{rule}"
    monkeypatch.setattr(script, "_GRANDFATHERED_ENTRIES", 2)
    assert script.problems(text) == []
    monkeypatch.setattr(script, "_GRANDFATHERED_ENTRIES", 1)
    found = script.problems(text)
    assert len(found) == 1
    assert "an entry has landed above it" in found[0]


def test_link_definitions_are_not_lines_of_the_body(script: ModuleType) -> None:
    """btclib-benchmarks ends its file with a block of reference links."""
    links = "".join(f"[iss{n}]: https://example.invalid/{n}\n" for n in range(9))
    assert script.problems(f"{_CLEAN}\n### Short\n\n- one\n\n{links}") == []


def test_every_entry_is_measured_where_the_rule_entry_is_released(
    script: ModuleType,
) -> None:
    """With no rule entry in the open section, the bound reaches every entry."""
    found = script.problems(f"{_CLEAN}\n### Long\n\n{_LONG}")
    assert len(found) == 1
    assert "'Long'" in found[0]


def test_main_reports_a_problem_and_returns_1(
    script: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`main()` prints the finding and exits 1, the shape the hook reads."""
    broken = tmp_path / "CHANGELOG.md"
    broken.write_text(_CLEAN.replace("Second entry", "First entry"), encoding="utf-8")
    monkeypatch.setattr(script, "_CHANGELOG", broken)
    assert script.main() == 1
    out = capsys.readouterr().out
    assert "repeats the heading" in out


def test_main_reports_nothing_wrong_and_returns_0(
    script: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A clean file prints one summary line and exits 0."""
    clean = tmp_path / "CHANGELOG.md"
    clean.write_text(_CLEAN, encoding="utf-8")
    monkeypatch.setattr(script, "_CHANGELOG", clean)
    assert script.main() == 0
    out = capsys.readouterr().out
    assert "repeats no heading" in out


def test_the_entry_point_guard_runs_the_check_as___main__(
    script: ModuleType,
) -> None:
    """The guard turns `main`'s return value into the process exit status.

    `runpy.run_path` executes the file again in this interpreter with
    `__name__` bound to `"__main__"`, the way
    `tests/sdist_exclude_test.py`'s own guard test does. It reads the
    real tree's own `CHANGELOG.md`, so the assertion is only that the
    guard agrees with `main()` on whatever that file holds.
    """
    with pytest.raises(SystemExit) as raised:
        runpy.run_path(str(_SCRIPT), run_name="__main__")

    assert raised.value.code == script.main()
