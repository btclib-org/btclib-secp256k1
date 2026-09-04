# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for the submodules-checked-out check of `.github/scripts`.

The check is a pre-commit hook, so what it says about the real tree is
answered on every commit, by the hook itself: there is deliberately no
test that the real tree passes it. What cannot be answered that way is
how it behaves against a tree it is not running in -- no .gitmodules at
all, a .gitmodules naming a submodule that is not checked out -- and
those are the cases here, built by hand.

The script is loaded by path, `.github/scripts` being no package, and
once: `monkeypatch` undoes what each test does to it.
"""

from __future__ import annotations

import importlib.util
import runpy
import sys
from pathlib import Path
from types import ModuleType

import pytest

_GITMODULES = """\
[submodule "secp256k1"]
\tpath = secp256k1
\turl = https://github.com/bitcoin-core/secp256k1.git
[submodule "secp256k1-zkp"]
\tpath = secp256k1-zkp
\turl = https://github.com/BlockstreamResearch/secp256k1-zkp.git
"""


def _load() -> ModuleType:
    """Import the check by path.

    Returns:
        The module.
    """
    path = (
        Path(__file__).parents[1]
        / ".github"
        / "scripts"
        / "check_submodules_checked_out.py"
    )
    spec = importlib.util.spec_from_file_location("check_submodules_checked_out", path)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


check = _load()


def _tree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    gitmodules: str = _GITMODULES,
    checked_out: tuple[str, ...] = ("secp256k1", "secp256k1-zkp"),
) -> None:
    """Stand a tree up in the answer the check reads.

    A tree with no .gitmodules at all is its own test, below, and does
    not go through this helper -- there is no "absent" value of a
    string to give it.

    Args:
        monkeypatch: the fixture the substitution is made through.
        tmp_path: stands in for the wrapper repository's root.
        gitmodules: .gitmodules's text.
        checked_out: which of the paths .gitmodules names get a `.git`
            of their own, standing in for an initialized submodule.
    """
    (tmp_path / ".gitmodules").write_text(gitmodules, encoding="utf-8")
    monkeypatch.setattr(check, "_ROOT", tmp_path)
    for path in checked_out:
        submodule = tmp_path / path
        submodule.mkdir(parents=True, exist_ok=True)
        (submodule / ".git").touch()


def test_the_paths_are_read_off_gitmodules() -> None:
    """Every "path = ..." line, in the order .gitmodules lists them."""
    assert check.submodule_paths(_GITMODULES) == ["secp256k1", "secp256k1-zkp"]
    assert check.submodule_paths("") == []
    assert check.submodule_paths("no submodule section here") == []


def test_every_submodule_checked_out_passes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The case the tree is in, and the only one that exits zero."""
    _tree(monkeypatch, tmp_path)
    assert check.main() == 0


def test_an_uninitialized_submodule_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A submodule with no `.git` of its own is not checked out."""
    _tree(monkeypatch, tmp_path, checked_out=("secp256k1",))

    assert check.main() == 1
    error = capsys.readouterr().err
    assert "secp256k1-zkp is not checked out" in error
    assert "git submodule update --init secp256k1-zkp" in error
    assert "secp256k1 is not checked out" not in error, (
        "the checked-out submodule stayed quiet on stderr"
    )


def test_every_uninitialized_submodule_is_named(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both missing submodules are reported, not only the first."""
    _tree(monkeypatch, tmp_path, checked_out=())

    assert check.main() == 1
    error = capsys.readouterr().err
    assert "secp256k1 is not checked out" in error
    assert "secp256k1-zkp is not checked out" in error


def test_no_gitmodules_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A repository with no .gitmodules is not the case this hook is for."""
    monkeypatch.setattr(check, "_ROOT", tmp_path)

    assert check.main() == 1
    assert ".gitmodules does not exist" in capsys.readouterr().err


def test_a_gitmodules_naming_no_submodule_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Nothing to check is a failure, not a vacuous pass.

    This is the shape in which a check quietly stops being one: with
    every submodule removed from .gitmodules, an implementation that
    skipped when it found none would report success from then on.
    """
    _tree(monkeypatch, tmp_path, gitmodules="no submodule section here")

    assert check.main() == 1
    assert ".gitmodules names no submodule" in capsys.readouterr().err


def test_checked_out_reads_the_filesystem_not_git(tmp_path: Path) -> None:
    """A directory with no `.git` is not checked out, whatever else is there.

    `-C <path>` does not stop git's own upward directory discovery when
    `<path>` has no `.git` of its own -- a fresh `git worktree add` does
    not initialize submodules, and the first `.git` discovery finds
    walking up from an uninitialized submodule is this wrapper
    repository's, one directory up. `checked_out` is what this check
    asks instead of ever running git in the submodule's own directory,
    so that discovery has nowhere to walk to.
    """
    submodule = tmp_path / "secp256k1"
    submodule.mkdir()
    assert check.checked_out(submodule) is False

    (submodule / ".git").touch()
    assert check.checked_out(submodule) is True

    assert check.checked_out(tmp_path / "does-not-exist") is False


def test_the_entry_point_guard_runs_the_check_as___main__() -> None:
    """The guard turns `main`'s return value into the process exit status.

    `runpy.run_path` executes the file again in this interpreter with
    `__name__` bound to `"__main__"`, which is what puts the guard's own
    line under test -- the way `tests/submodule_pin_test.py`'s own guard
    test does, over the pin check's entry point. Unlike that check, this
    one calls no subprocess, so there is nothing global to stub into a
    chosen answer; `_ROOT` is computed from `__file__` inside the freshly
    executed copy the same way it is in the one this test file already
    imported, so both read the real checkout's own .gitmodules and the
    real submodules' checked-out state. The assertion is that the guard
    agrees with `main()` on whatever that state is, not that either
    answers a fixed value -- this is not a test that the real tree
    passes the check, only that the guard reports what `main()` reports.
    """
    path = (
        Path(__file__).parents[1]
        / ".github"
        / "scripts"
        / "check_submodules_checked_out.py"
    )

    with pytest.raises(SystemExit) as raised:
        runpy.run_path(str(path), run_name="__main__")

    assert raised.value.code == check.main()
