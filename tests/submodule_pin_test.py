# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for the submodule pin check of `.github/scripts`.

The check is a pre-commit hook, so what it says about the real tree is
answered on every commit and in the lint workflow, by the hook itself.
What cannot be answered that way is how it behaves when the answer is no
-- a pin that is not what README.md names, a README naming nothing, a
submodule nobody initialized -- because a tree in any of those states is
a tree the gate refuses. Those are the cases here, built by hand.

There is deliberately no test that the real tree passes the check
itself: that is the hook's own job, and it runs on every commit. The
entry-point guard below is built by hand too, `check.subprocess.run`
stubbed to fail every call the way the rest of this file already stubs
`_git` or `check.subprocess.run` directly, so the guard's own run is as
independent of the checkout's actual state -- submodule included -- as
every other test here.

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

_PINNED = "6e2c8bc4ecdc6e71dbe7a368f360d8d453ce435d"
_OTHER = "1a53f4907d5b8f7b0e5b1d3e33e3e50b0e1f0d5c"
_ZKP_PINNED = "10366dbbbfeb11457f2aae3b23e154ab7d6a1fe4"
_ZKP_OTHER = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
_README = (
    "wraps ([v0.8.0](https://github.com/bitcoin-core/secp256k1/releases/tag/v0.8.0))."
    " zkp at [10366dbb](https://github.com/BlockstreamResearch/secp256k1-zkp/commit/"
    "10366dbbbfeb11457f2aae3b23e154ab7d6a1fe4)."
)


def _load() -> ModuleType:
    """Import the check by path.

    Returns:
        The module.
    """
    path = Path(__file__).parents[1] / ".github" / "scripts" / "check_submodule_pin.py"
    spec = importlib.util.spec_from_file_location("check_submodule_pin", path)
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
    readme: str = _README,
    pinned: str | None = _PINNED,
    tagged: str | None = _PINNED,
    zkp_pinned: str | None = _ZKP_PINNED,
) -> None:
    """Stand a tree up in the answers the check reads, both halves.

    The defaults are the agreeing case for each half, so each test below
    names the one answer it changes and the reader sees which that is. A
    test exercising only the release half leaves the zkp half agreeing by
    default, and the other way round.

    Args:
        monkeypatch: the fixture the substitutions are made through.
        tmp_path: where the README the check reads is written.
        readme: its text.
        pinned: what the secp256k1 gitlink says, or None for no submodule
            at all.
        tagged: what the tag resolves to, or None for a tag the vendored
            clone does not have.
        zkp_pinned: what the secp256k1-zkp gitlink says, or None for no
            submodule at all.
    """
    (tmp_path / "README.md").write_text(readme, encoding="utf-8")
    monkeypatch.setattr(check, "_ROOT", tmp_path)

    def _pinned_commit(submodule: str = check._SUBMODULE) -> str | None:
        return zkp_pinned if submodule == check._SUBMODULE_ZKP else pinned

    monkeypatch.setattr(check, "pinned_commit", _pinned_commit)
    monkeypatch.setattr(check, "commit_of", lambda _tag: tagged)


def test_the_release_is_read_off_the_url() -> None:
    """The tag is the one README.md links to, and the first of them."""
    assert check.named_release(_README) == "v0.8.0"
    assert check.named_release("v0.7.1 in prose, no link") is None
    assert check.named_release("") is None
    # the first link wins: the sentence naming what is wrapped opens the
    # file, and a later link to an older release is prose about history
    older = "[v0.7.1](https://github.com/bitcoin-core/secp256k1/releases/tag/v0.7.1)"
    assert check.named_release(f"{_README} up from {older}") == "v0.8.0"


def test_a_link_placed_before_the_named_one_wins_instead() -> None:
    """First is a position, not an identity (btclib-org/btclib-secp256k1#429).

    Nothing here tells a stale link from a current one by shape: both are
    `secp256k1/releases/tag/vX.Y.Z`, and `named_release` reads whichever
    comes first in the file. The tree relies on "## Versioning"'s link
    being the only one, not on it being the right one by some other mark
    -- so a second, older link placed *before* it silently becomes the
    release every check compares the submodule against, with no error
    anywhere. This is the reverse of the case above, which places the
    older link after and finds it inert.
    """
    older = "[v0.7.1](https://github.com/bitcoin-core/secp256k1/releases/tag/v0.7.1)"
    assert check.named_release(f"{older} came before {_README}") == "v0.7.1"


def test_a_pin_matching_the_named_release_passes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The case the tree is in, and the only one that exits zero."""
    _tree(monkeypatch, tmp_path)
    assert check.main() == 0


def test_a_pin_that_is_not_the_named_release_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A submodule moved without the prose, or prose without the submodule.

    Both abbreviations are in the message, because which of the two
    happened is not something the check can know, and is the whole of
    what its reader has to decide.
    """
    _tree(monkeypatch, tmp_path, pinned=_OTHER)

    assert check.main() == 1
    error = capsys.readouterr().err
    assert "v0.8.0" in error
    assert _PINNED[:7] in error
    assert _OTHER[:7] in error


def test_a_readme_naming_no_release_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Nothing to compare against is a failure, not a pass.

    This is the shape in which a check quietly stops being one: with the
    link gone, an implementation that skipped when it found no tag would
    report success on every commit thereafter.
    """
    _tree(monkeypatch, tmp_path, readme="no link here")

    assert check.main() == 1
    assert "links to no libsecp256k1 release" in capsys.readouterr().err


@pytest.mark.parametrize(
    "answers, expected",
    [
        ({}, "is not checked out"),
        ({"--is-shallow-repository": "true"}, "is shallow"),
        ({"--is-shallow-repository": "false"}, "neither absent nor shallow"),
    ],
)
def test_a_clone_without_the_tag_says_which_of_the_three_it_is(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    answers: dict[str, str],
    expected: str,
) -> None:
    """No tag has three causes, and one message for all three said none.

    A developer has one of the three and knows which; a checkout somebody
    else makes does not, and there which one it is *is* the finding. It
    was pre-commit.ci that made that concrete: told to take the submodule
    it takes it, and the hook failed anyway with a message that could not
    say whether the clone was missing or merely shallow.

    Args:
        monkeypatch: the fixture the substitutions are made through.
        tmp_path: where the README the check reads is written.
        capsys: the captured streams.
        answers: what git answers each question, by its last argument; a
            question missing from it is a git that exited non-zero. An
            empty dict is also the signal to leave `secp256k1/.git`
            absent, `why_no_tag` reading that state off the filesystem
            rather than asking git.
        expected: the clause the message has to carry.
    """
    _tree(monkeypatch, tmp_path, tagged=None)
    if answers:
        (tmp_path / "secp256k1").mkdir()
        (tmp_path / "secp256k1" / ".git").touch()
    monkeypatch.setattr(check, "_git", lambda *args, **_kwargs: answers.get(args[-1]))

    assert check.main() == 1
    assert expected in capsys.readouterr().err


def test_git_is_never_asked_when_the_submodule_has_no_git_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A missing `secp256k1/.git` is read from the filesystem, not asked of git.

    `-C secp256k1` does not stop git's own upward directory discovery
    when `secp256k1/` has no `.git` -- a fresh `git worktree add` does
    not initialize submodules, and the first `.git` discovery finds
    walking up from an uninitialized `secp256k1/` is this wrapper
    repository's, one directory up. Never calling git at all for that
    question is what keeps that discovery from having anywhere to run;
    a stub that raises is what makes a regression here fail loudly
    rather than pass by resolving against the wrong repository.

    Args:
        monkeypatch: the fixture the substitutions are made through.
        tmp_path: stands in for the wrapper repository's root.
    """
    monkeypatch.setattr(check, "_ROOT", tmp_path)
    (tmp_path / "secp256k1").mkdir()

    def _unreachable(*args: str, **_kwargs: Any) -> str:
        raise AssertionError(f"git must not run when secp256k1/.git is absent: {args}")

    monkeypatch.setattr(check, "_git", _unreachable)

    assert check.commit_of("v0.8.0") is None
    assert "is not checked out" in check.why_no_tag("v0.8.0")


def test_a_tree_with_no_submodule_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The gitlink is the first thing read, and its absence is the answer."""
    _tree(monkeypatch, tmp_path, pinned=None)

    assert check.main() == 1
    assert "no secp256k1 submodule" in capsys.readouterr().err


def test_the_zkp_commit_is_read_off_the_url() -> None:
    """The zkp pin is the one README.md links to, and the first of them."""
    assert check.named_zkp_commit(_README) == _ZKP_PINNED
    assert check.named_zkp_commit("no link here") is None
    assert check.named_zkp_commit("") is None


def test_a_zkp_pin_matching_the_named_commit_passes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The case the tree is in, for the half with no release to name."""
    _tree(monkeypatch, tmp_path)
    assert check.main() == 0


def test_a_zkp_pin_that_is_not_the_named_commit_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A submodule moved without the prose, or prose without the submodule.

    The release half agrees here, so this is the zkp half's own failure
    message, not the release half's.
    """
    _tree(monkeypatch, tmp_path, zkp_pinned=_ZKP_OTHER)

    assert check.main() == 1
    error = capsys.readouterr().err
    assert _ZKP_PINNED[:7] in error
    assert _ZKP_OTHER[:7] in error
    assert "v0.8.0" not in error, "the release half agreed and stayed quiet on stderr"


def test_a_readme_naming_no_zkp_commit_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No zkp link is a failure, the same way no release link is."""
    _tree(monkeypatch, tmp_path, readme=_README.split(" zkp at", maxsplit=1)[0])

    assert check.main() == 1
    assert "links to no secp256k1-zkp commit" in capsys.readouterr().err


def test_a_tree_with_no_zkp_submodule_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The zkp gitlink is the first thing that half reads too."""
    _tree(monkeypatch, tmp_path, zkp_pinned=None)

    assert check.main() == 1
    assert "no secp256k1-zkp submodule" in capsys.readouterr().err


def test_both_halves_disagreeing_report_both(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A single failing commit names every pin that disagrees, not the first."""
    _tree(monkeypatch, tmp_path, pinned=_OTHER, zkp_pinned=_ZKP_OTHER)

    assert check.main() == 1
    error = capsys.readouterr().err
    assert _OTHER[:7] in error
    assert _ZKP_OTHER[:7] in error


def test_the_submodule_is_read_with_the_hook_environment_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`-C secp256k1` does not override GIT_DIR, so the environment must.

    git hands a hook GIT_DIR and GIT_INDEX_FILE naming the repository
    being committed to, and they win over `-C`: the tag is then looked
    for in this repository, which has none of libsecp256k1's, and comes
    back missing. It shows from the git hook and nowhere else -- a
    `pre-commit run` in a terminal sets neither, and passed on the very
    tree the commit then refused -- so what holds it is here rather than
    a run that would have to be made from one.

    The other direction is asserted too: the call that reads the pin
    keeps the environment, GIT_INDEX_FILE being how git tells a hook
    which index is about to be committed.

    Args:
        monkeypatch: the fixture the environment and the stub are set
            through.
    """
    captured: list[dict[str, str] | None] = []

    class _Result:
        returncode = 0
        stdout = ""

    def fake_run(_args: list[str], **kwargs: Any) -> _Result:
        env: dict[str, str] | None = kwargs.get("env")
        captured.append(env)
        return _Result()

    monkeypatch.setenv("GIT_DIR", "/elsewhere/.git")
    monkeypatch.setenv("GIT_INDEX_FILE", "/elsewhere/.git/index")
    monkeypatch.setattr(check.subprocess, "run", fake_run)
    # this test is about the environment a real git call is made with, not
    # about whether the submodule is checked out -- true in the job that
    # gates coverage on this file, false in the sdist install jobs, which
    # check this repository out in full but the submodule not at all
    monkeypatch.setattr(check, "_checked_out", lambda _path: True)

    check.commit_of("v0.8.0")
    submodule_env = captured[-1]
    assert submodule_env is not None, "the submodule call passes an environment"
    assert "GIT_DIR" not in submodule_env
    assert "GIT_INDEX_FILE" not in submodule_env
    # something is left: the environment is filtered, not emptied
    assert submodule_env

    check.pinned_commit()
    assert captured[-1] is None, "the pin is read from the index git names"


def test_pinned_commit_reads_the_gitlink_line_git_prints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The four-field, mode-160000 line is what tells a submodule from a file.

    Every other test stubs `pinned_commit` itself, so nothing above ever
    runs its own parsing of the `git ls-files --stage` line. Both shapes
    are exercised here: the gitlink `git` actually prints for a submodule,
    and a same-named ordinary file, which the mode alone tells apart.

    Args:
        monkeypatch: the fixture `_git` is replaced through.
    """
    gitlink = f"160000 {_PINNED} 0\tsecp256k1"
    monkeypatch.setattr(check, "_git", lambda *_args, **_kwargs: gitlink)
    assert check.pinned_commit() == _PINNED

    ordinary_file = f"100644 {_PINNED} 0\tsecp256k1"
    monkeypatch.setattr(check, "_git", lambda *_args, **_kwargs: ordinary_file)
    assert check.pinned_commit() is None


def test_pinned_commit_reads_whichever_submodule_it_is_asked_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The path argument is threaded to `_git`, not the default silently kept.

    A `pinned_commit` that read `_SUBMODULE` internally instead of its own
    `submodule` parameter would pass this test's default call and fail
    silently on the zkp one -- this is the regression that guards the
    parametrization itself, not only its default.
    """
    seen: list[str] = []

    def _git(*args: str, **_kwargs: object) -> str:
        seen.append(args[-1])
        return f"160000 {_ZKP_PINNED} 0\t{args[-1]}"

    monkeypatch.setattr(check, "_git", _git)
    assert check.pinned_commit(check._SUBMODULE_ZKP) == _ZKP_PINNED
    assert seen == [check._SUBMODULE_ZKP]


def test_the_entry_point_guard_runs_the_check_as___main__(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The guard turns `main`'s return value into the process exit status.

    `runpy.run_path` executes the file again in this interpreter with
    `__name__` bound to `"__main__"`, which is what puts the guard's own
    line under test; a subprocess would run it in an interpreter this
    suite measures nothing in. `check.subprocess` is the real stdlib
    module the freshly executed copy also imports, the way
    `tests/vendored_vectors_test.py`'s own guard test stubs the same
    module, so failing every call through it here makes `pinned_commit`
    answer `None` and pins both the exit code and the message -- with no
    real `git` process run and no dependence on whether the environment
    running this test has the submodule checked out.

    Args:
        monkeypatch: the fixture `subprocess.run` is replaced through.
        capsys: the captured streams.
    """
    path = Path(__file__).parents[1] / ".github" / "scripts" / "check_submodule_pin.py"

    class _Result:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(check.subprocess, "run", lambda *_args, **_kwargs: _Result())

    with pytest.raises(SystemExit) as raised:
        runpy.run_path(str(path), run_name="__main__")

    assert raised.value.code == 1
    assert "no secp256k1 submodule in this tree" in capsys.readouterr().err
