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
exclude = [
    "/COPYRIGHT",
    "secp256k1/configure",
    "secp256k1/autotools-aux/ar-lib",
]

[tool.ruff]
# a second, unrelated exclude array, elsewhere in the file
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


def test_no_sdist_table_returns_empty() -> None:
    """No table to read is an empty list, the same as an empty array."""
    assert check.sdist_exclude_patterns('[project]\nname = "x"\n') == []


def test_a_sdist_table_with_no_exclude_key_returns_empty() -> None:
    """The table without the key is the same absence as no table at all."""
    text = "[tool.hatch.build.targets.sdist]\n# no exclude here\n\n[tool.ruff]\n"
    assert check.sdist_exclude_patterns(text) == []


def test_text_that_is_no_toml_is_refused() -> None:
    """An array with no `]` is no TOML, and no pattern set is read from it."""
    truncated = '[tool.hatch.build.targets.sdist]\nexclude = [\n    "/COPYRIGHT",\n'
    assert check.sdist_exclude_patterns(truncated) is None


def test_an_exclude_that_is_not_an_array_of_strings_is_refused() -> None:
    """A string, or an array holding anything but strings, is no pattern list.

    hatchling refuses both, so neither is a list check-sdist's plugin
    subtracts, and a check matching whatever part of it is a string
    answers about a list nobody builds with.
    """
    string = '[tool.hatch.build.targets.sdist]\nexclude = "/COPYRIGHT"\n'
    mixed = '[tool.hatch.build.targets.sdist]\nexclude = ["/COPYRIGHT", 1]\n'
    assert check.sdist_exclude_patterns(string) is None
    assert check.sdist_exclude_patterns(mixed) is None


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


def test_main_fails_when_the_exclude_list_cannot_be_read(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A list the check cannot read is a failure, never a quiet pass.

    Read as no entries at all, the exclude a tracked file matches would
    match nothing, and the hook would pass on the very defect it exists
    for.
    """
    _tree(
        monkeypatch,
        tmp_path,
        pyproject='[tool.hatch.build.targets.sdist]\nexclude = "secp256k1/autotools-aux"\n',
        tracked=["secp256k1/autotools-aux/m4/bitcoin_secp.m4"],
    )

    assert check.main() == 1
    assert "not an array of strings" in capsys.readouterr().err


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
