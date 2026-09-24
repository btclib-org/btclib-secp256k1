# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for the sdist-exclude check of `.github/scripts`.

The check is a pre-commit hook, so what it says about the real tree is
answered on every commit, by the hook itself: there is deliberately no
test that the real tree passes it. What cannot be answered that way is
how it behaves against an exclude list that does what
btclib-org/btclib-secp256k1#655 describes -- an entry matching a tracked
file -- because a tree in that state is a tree the gate refuses. Those
cases are built by hand, alongside `/COPYRIGHT`'s own deliberate one,
which the real tree carries and which the check has to stay quiet about.

`_DELIBERATE` is what tells the two apart, so `_tree` below sets it per
case rather than leaving the real tuple in place: a fixture tree whose
tracked files do not include `COPYRIGHT` would otherwise fail on the
exemption matching nothing, which is a real failure of the real tree and
not of the case under test.

One test does read the real `pyproject.toml`: the canary asserting that
`sdist_exclude_patterns` returns exactly what `tomllib` reads out of
the same file. That is not the hook's own question -- it asks whether
the walk is still reading the array TOML says is there, which is the
one thing a hook matching a substituted pattern set could not report.
The script parses by hand and the canary is `importorskip`ped rather
than written into the script; moving the script to `tomllib` is
btclib-org/btclib-secp256k1#994.

The script is loaded by path, `.github/scripts` being no package, and
once: `monkeypatch` undoes what each test does to it.
"""

from __future__ import annotations

import importlib.util
import runpy
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_PYPROJECT = """\
[project]
name = "btclib-secp256k1"

[tool.hatch.build.targets.sdist]
# a comment above the array, holding a quote that must not leak in:
# .gitignore excludes "**/.DS_Store" but not "**/.DS_Store?"
exclude = [
    "/COPYRIGHT",
    "secp256k1/configure",
    "secp256k1/autotools-aux/ar-lib",
]

[tool.ruff]
# a second, unrelated "exclude = [" array, elsewhere in the file: the
# section regex must not wander into it
exclude = ["docs/", "build/"]

[tool.mypy]
exclude = ["scripts/"]
"""


def _load() -> ModuleType:
    """Import the check by path.

    Returns:
        The module.
    """
    path = Path(__file__).parents[1] / ".github" / "scripts" / "check_sdist_exclude.py"
    spec = importlib.util.spec_from_file_location("check_sdist_exclude", path)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


check = _load()


def test_the_sdist_section_is_read_and_the_others_are_not() -> None:
    """Only `[tool.hatch.build.targets.sdist]`'s own array comes back."""
    assert check.sdist_exclude_patterns(_PYPROJECT) == [
        "/COPYRIGHT",
        "secp256k1/configure",
        "secp256k1/autotools-aux/ar-lib",
    ]


def test_a_comment_sharing_a_line_with_the_array_is_not_an_entry() -> None:
    """A quote inside a whole-line comment above the array does not leak in."""
    patterns = check.sdist_exclude_patterns(_PYPROJECT)
    assert ".DS_Store" not in "".join(patterns)


def test_a_bracket_inside_an_in_array_comment_does_not_close_it_early() -> None:
    """The real file's own comment cites `[tool.check-sdist]`, brackets and all.

    A single regex spanning "the first `]` after the opening one" would
    stop here, on the comment's own `]`, and silently drop every entry
    written after it; the real file's array carries such a comment
    between two entries.
    """
    text = (
        "[tool.hatch.build.targets.sdist]\nexclude = [\n"
        '    "/COPYRIGHT",\n'
        "    # ... its hatchling plugin reading this very list"
        " ([tool.check-sdist] below) ...\n"
        '    "secp256k1/configure",\n]\n'
    )
    assert check.sdist_exclude_patterns(text) == ["/COPYRIGHT", "secp256k1/configure"]


def test_no_sdist_table_returns_empty() -> None:
    """No table to read is an empty list, the same as an empty array."""
    assert check.sdist_exclude_patterns('[project]\nname = "x"\n') == []


def test_a_sdist_table_with_no_exclude_key_returns_empty() -> None:
    """The table without the key is the same absence as no table at all."""
    text = "[tool.hatch.build.targets.sdist]\n# no exclude here\n\n[tool.ruff]\n"
    assert check.sdist_exclude_patterns(text) == []


def test_an_inline_array_is_refused_rather_than_read() -> None:
    """The shape `[tool.ruff]`'s and `[tool.mypy]`'s own arrays are written in.

    Read rather than refused, the walk never leaves the array: it runs
    off the end of the table and takes every double-quoted string down
    to the next line reading only `]`, so it answers with a pattern set
    assembled out of whatever tables follow.
    """
    text = (
        "[tool.hatch.build.targets.sdist]\n"
        'exclude = ["/COPYRIGHT", "secp256k1/configure"]\n'
        "\n[tool.ruff]\n"
        'lint = ["E", "F"]\n]\n'
    )
    assert check.sdist_exclude_patterns(text) is None


def test_an_array_not_closed_on_a_line_of_its_own_is_refused() -> None:
    """A `]` sharing its line with a comment does not close the array.

    Nor does an array with no `]` at all. Both leave the walk inside the
    array at the end of the file, which is the same refusal: what
    follows the table would otherwise be read as further entries.
    """
    commented = (
        "[tool.hatch.build.targets.sdist]\nexclude = [\n"
        '    "/COPYRIGHT",\n]  # the array closes here\n'
    )
    truncated = '[tool.hatch.build.targets.sdist]\nexclude = [\n    "/COPYRIGHT",\n'
    assert check.sdist_exclude_patterns(commented) is None
    assert check.sdist_exclude_patterns(truncated) is None


def test_an_entry_that_is_not_one_double_quoted_string_is_refused() -> None:
    """TOML's other string forms, and an entry sharing its line.

    A literal-string entry carries no double quote, so a reader looking
    for double-quoted runs drops it and answers a list short of the
    entry that is there. A comment sharing the line with an entry is the
    other way round: the quoted path inside the comment becomes a
    further pattern the array does not hold.
    """
    literal = (
        "[tool.hatch.build.targets.sdist]\nexclude = [\n"
        "    'secp256k1/autotools-aux',\n]\n"
    )
    commented = (
        "[tool.hatch.build.targets.sdist]\nexclude = [\n"
        '    "secp256k1/configure",  # and "secp256k1/src" is kept\n]\n'
    )
    two_on_a_line = (
        "[tool.hatch.build.targets.sdist]\nexclude = [\n"
        '    "/COPYRIGHT", "/build",\n]\n'
    )
    assert check.sdist_exclude_patterns(literal) is None
    assert check.sdist_exclude_patterns(commented) is None
    assert check.sdist_exclude_patterns(two_on_a_line) is None


def test_a_blank_line_between_entries_is_read_through() -> None:
    """A blank line separates entries without ending or breaking the array."""
    text = (
        "[tool.hatch.build.targets.sdist]\nexclude = [\n"
        '    "/COPYRIGHT",\n\n    "secp256k1/configure",\n]\n'
    )
    assert check.sdist_exclude_patterns(text) == ["/COPYRIGHT", "secp256k1/configure"]


def test_the_walk_reads_of_the_real_file_what_tomllib_reads() -> None:
    """The canary: this walk and a TOML parser agree on `pyproject.toml`.

    Every test above builds its own text, so none of them would notice
    the real array being rewritten into a shape the walk reads as a
    different list -- and a hook matching a different list is green on a
    question nobody asked. `tomllib` answers what TOML says is there.
    """
    tomllib = pytest.importorskip("tomllib")
    path = Path(__file__).parents[1] / "pyproject.toml"
    text = path.read_text(encoding="utf-8")
    parsed = tomllib.loads(text)["tool"]["hatch"]["build"]["targets"]["sdist"]

    assert check.sdist_exclude_patterns(text) == parsed["exclude"]


def test_tracked_files_runs_git_ls_files_recursing_submodules(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The exact command the loss this hook exists for depends on."""
    captured: dict[str, Any] = {}

    class _Result:
        returncode = 0
        stdout = "a\nsecp256k1/b\n"

    def fake_run(args: list[str], **kwargs: Any) -> _Result:
        captured["args"] = args
        captured["cwd"] = kwargs.get("cwd")
        return _Result()

    monkeypatch.setattr(check.subprocess, "run", fake_run)

    assert check.tracked_files(tmp_path) == ["a", "secp256k1/b"]
    assert captured["args"] == [
        check._GIT,
        "ls-files",
        "--cached",
        "--recurse-submodules",
    ]
    assert captured["cwd"] == tmp_path


def test_tracked_files_returns_none_on_a_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A git failure is reported, not read as an empty tree."""

    class _Result:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(check.subprocess, "run", lambda *_a, **_k: _Result())

    assert check.tracked_files(tmp_path) is None


def test_excluded_tracked_files_matches_the_issues_own_reproduction() -> None:
    """A directory-level entry catches the file it was meant to be a file.

    The exact case btclib-org/btclib-secp256k1#655 measured: a
    directory-level exclude entry for one submodule's aux directory
    matches its tracked file, and the other submodule's identically
    named file, which the entry does not name, is the control that the
    match is not vacuous.
    """
    exclude = ["secp256k1/autotools-aux"]
    files = [
        "secp256k1/autotools-aux/m4/bitcoin_secp.m4",
        "secp256k1-zkp/autotools-aux/m4/bitcoin_secp.m4",
        "secp256k1/src/secp256k1.c",
    ]
    assert check.excluded_tracked_files(exclude, files) == [
        "secp256k1/autotools-aux/m4/bitcoin_secp.m4"
    ]


def test_excluded_tracked_files_is_empty_for_the_real_lists_own_shape() -> None:
    """A flat-file entry naming a local build's own debris matches nothing.

    This is the ordinary case the exclude list was written for: an entry
    naming a file `./autogen.sh && ./configure` writes and no clone
    tracks, which is why the real list fails nothing today.
    """
    exclude = ["secp256k1/configure", "secp256k1/autotools-aux/ar-lib"]
    files = ["secp256k1/src/secp256k1.c", "secp256k1/autotools-aux/m4/bitcoin_secp.m4"]
    assert check.excluded_tracked_files(exclude, files) == []


def _tree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    pyproject: str = _PYPROJECT,
    deliberate: tuple[str, ...] = (),
    tracked: list[str] | None,
) -> None:
    """Stand a tree up in the answers the check reads.

    Args:
        monkeypatch: the fixture the substitutions are made through.
        tmp_path: stands in for the wrapper repository's root.
        pyproject: pyproject.toml's text.
        deliberate: the exemptions, standing in for the real tuple --
            empty unless the case is about one, since a member matched
            by nothing is itself a failure.
        tracked: what `tracked_files` answers -- None stands in for a
            failed `git ls-files`.
    """
    (tmp_path / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    monkeypatch.setattr(check, "_ROOT", tmp_path)
    monkeypatch.setattr(check, "_DELIBERATE", deliberate)
    monkeypatch.setattr(check, "tracked_files", lambda _root: tracked)


def test_main_passes_when_no_entry_matches_a_tracked_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The ordinary case: every entry names something no clone carries."""
    _tree(monkeypatch, tmp_path, tracked=["secp256k1/src/secp256k1.c"])

    assert check.main() == 0
    out = capsys.readouterr().out
    assert "only the deliberate sdist exclude entries match a tracked file" in out


def test_main_stays_quiet_about_a_deliberate_exclusion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`/COPYRIGHT` is tracked and matches the list's first entry on purpose.

    This is what the exemption buys, and the real tree is in exactly
    this state: without it the check reports the one drop this
    repository asks for.
    """
    _tree(
        monkeypatch,
        tmp_path,
        deliberate=("COPYRIGHT",),
        tracked=["COPYRIGHT", "secp256k1/src/secp256k1.c"],
    )

    assert check.main() == 0


def test_main_fails_when_an_exemption_matches_no_tracked_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An exemption for a drop that is not happening is a failure too.

    It is what stops the exemptions being a second list to keep in step
    by hand: an entry removed from `exclude` and left named here would
    otherwise sit there permitting a later entry to take that file out
    of the sdist unreported.
    """
    _tree(
        monkeypatch,
        tmp_path,
        pyproject=(
            "[tool.hatch.build.targets.sdist]\nexclude = [\n"
            '    "secp256k1/configure",\n]\n'
        ),
        deliberate=("COPYRIGHT",),
        tracked=["COPYRIGHT", "secp256k1/src/secp256k1.c"],
    )

    assert check.main() == 1
    error = capsys.readouterr().err
    assert "COPYRIGHT" in error
    assert "#770" in error


def test_main_passes_with_an_empty_exclude_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Nothing to exclude matches nothing, by construction -- not a failure.

    Unlike `check_submodules_checked_out.py`'s "nothing to check", an
    empty exclude list answers this hook's actual question -- does any
    entry match a tracked file -- correctly and completely: there is no
    entry, so there is no match, and no possible false green hides
    behind that answer.
    """
    _tree(
        monkeypatch,
        tmp_path,
        pyproject="[tool.hatch.build.targets.sdist]\nexclude = [\n]\n",
        tracked=["secp256k1/src/secp256k1.c"],
    )

    assert check.main() == 0


def test_main_fails_when_an_entry_matches_a_submodule_tracked_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """btclib-org/btclib-secp256k1#655's own reproduction, through `main`."""
    _tree(
        monkeypatch,
        tmp_path,
        pyproject=(
            "[tool.hatch.build.targets.sdist]\nexclude = [\n"
            '    "secp256k1/autotools-aux",\n]\n'
        ),
        tracked=["secp256k1/autotools-aux/m4/bitcoin_secp.m4"],
    )

    assert check.main() == 1
    error = capsys.readouterr().err
    assert "secp256k1/autotools-aux/m4/bitcoin_secp.m4" in error
    assert "#655" in error


def test_main_fails_when_an_entry_matches_a_tracked_file_outside_a_submodule(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The unanchored spelling of the entry that drops the built extension.

    `pyproject.toml`'s own comment on `/_btclib_secp256k1.*` names this:
    without the leading `/` the pattern also matches the tracked
    `stubs/_btclib_secp256k1.pyi`, which the strict mypy gate needs, and
    check-sdist subtracts that match rather than reporting it. The file
    sits outside every submodule, which is the class a scope reading
    only those cannot answer about (btclib-org/btclib-secp256k1#770).
    """
    _tree(
        monkeypatch,
        tmp_path,
        pyproject=(
            "[tool.hatch.build.targets.sdist]\nexclude = [\n"
            '    "_btclib_secp256k1.*",\n]\n'
        ),
        tracked=["stubs/_btclib_secp256k1.pyi", "secp256k1/src/secp256k1.c"],
    )

    assert check.main() == 1
    error = capsys.readouterr().err
    assert "stubs/_btclib_secp256k1.pyi" in error
    assert "#655" in error


def test_main_fails_when_the_exclude_array_is_outside_what_it_reads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An array the walk cannot read is a failure, never a quiet pass.

    The inline shape is the one that matters: read as far as the walk
    would take it, this tree's own exclude list turns into the strings
    of whatever tables follow, and the entry #655 is about is not among
    them -- so the hook would pass on the very defect it exists for.
    """
    _tree(
        monkeypatch,
        tmp_path,
        pyproject=(
            '[tool.hatch.build.targets.sdist]\nexclude = ["secp256k1/autotools-aux"]\n'
        ),
        tracked=["secp256k1/autotools-aux/m4/bitcoin_secp.m4"],
    )

    assert check.main() == 1
    assert "outside what this check reads" in capsys.readouterr().err


def test_main_fails_when_git_ls_files_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A git failure is a check that cannot answer, not a pass."""
    _tree(monkeypatch, tmp_path, tracked=None)

    assert check.main() == 1
    assert "git ls-files" in capsys.readouterr().err


def test_the_entry_point_guard_runs_the_check_as___main__() -> None:
    """The guard turns `main`'s return value into the process exit status.

    `runpy.run_path` executes the file again in this interpreter with
    `__name__` bound to `"__main__"`, the way
    `tests/submodules_checked_out_test.py`'s own guard test does. Unlike
    that check, this one reads the real checkout's own pyproject.toml
    and tracked files, so the assertion is only that the guard agrees
    with `main()` on whatever that state is -- this is not
    a test that the real tree passes the check, only that the guard
    reports what `main()` reports.
    """
    path = Path(__file__).parents[1] / ".github" / "scripts" / "check_sdist_exclude.py"

    with pytest.raises(SystemExit) as raised:
        runpy.run_path(str(path), run_name="__main__")

    assert raised.value.code == check.main()
