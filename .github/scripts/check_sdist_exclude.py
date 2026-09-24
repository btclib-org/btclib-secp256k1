# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""No sdist `exclude` entry matches a tracked file, bar the deliberate ones.

check-sdist (henryiii/check-sdist) compares the sdist hatchling builds
against `git ls-files --cached --recurse-submodules`, and its hatchling
plugin then subtracts from that comparison whatever
`[tool.hatch.build.targets.sdist]`'s own `exclude` list matches
(`check_sdist/backends/hatchling.py`'s `git_only_excludes`, called
unconditionally inside `compare()` at v1.6.0, regardless of
`[tool.check-sdist]`'s `mode`). An entry matching a tracked file
therefore drops that file from the sdist with check-sdist quiet about
it, whatever the file is and wherever it lives
(btclib-org/btclib-secp256k1#655).

Some of that subtraction is meant, and `_DELIBERATE` below is where the
file it drops on purpose is named. That tuple is what lets this check
match the exclude list against every tracked file rather than against a
subset picked to leave `/COPYRIGHT` out: a match outside it fails, and
so does a member of it the list matches nothing for, so it cannot drift
from the list it names exemptions from
(btclib-org/btclib-secp256k1#770).

Every tracked file is the scope because this repository's own sources
are as reachable by a hand-written entry as a submodule's are:
`/_btclib_secp256k1.*` is anchored, and `pyproject.toml`'s comment
beside it names the tracked `stubs/_btclib_secp256k1.pyi` that the
unanchored spelling takes out of the sdist -- a file the strict mypy
gate needs. This check fails on that spelling.

It fires only where an entry matches a file that is *currently tracked*,
so an entry naming a local build's own debris, which is untracked,
leaves it quiet: most of the list names what `./autogen.sh &&
./configure` writes inside a submodule, and no clone carries any of it.
That asymmetry is also why `[tool.check-sdist]`'s `mode = "all"` -- one
of the two other answers #655 named and did not choose between -- is not
this one: `mode` decides what `compare()` treats as "git" (`git ls-files`
under `"git"`, every file on disk under `"all"`), but `git_only_excludes`
runs after that choice and unconditionally either way, so it subtracts
the same tracked file under both -- measured against
`check_sdist/__main__.py`'s own `compare()`, `mode` never reaching that
call at all. The third, an upstream request that the plugin report what
it subtracts, remains open against henryiii/check-sdist and would retire
this hook if it landed; nothing here depends on it landing.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pathspec

# resolved once, the same way check_submodule_pin.py's own _GIT is: a
# bare "git" in a subprocess list is what S607 is about
_GIT = shutil.which("git") or "git"

_ROOT = Path(__file__).resolve().parents[2]

# the tracked files the exclude list drops from the sdist on purpose,
# spelled as `git ls-files` prints them rather than as the entry that
# drops them is written. Each has its reason beside that entry in
# pyproject.toml; main() below is what keeps the two in step
_DELIBERATE = ("COPYRIGHT",)


def sdist_exclude_patterns(pyproject_toml: str) -> list[str] | None:
    """Return `[tool.hatch.build.targets.sdist]`'s `exclude` list.

    Args:
        pyproject_toml: the file's text.

    Returns:
        The list, in the order it is written; an empty one where the
        table or the key is absent -- the same fallback check-sdist's
        own hatchling plugin (`git_only_excludes`) uses, so this reads
        the identical question it answers; or None where the file is no
        TOML or the value is not an array of strings, which is a check
        that cannot answer rather than a check that passes.
    """
    try:
        parsed = tomllib.loads(pyproject_toml)
    except tomllib.TOMLDecodeError:
        return None
    target = parsed.get("tool", {}).get("hatch", {}).get("build", {})
    exclude = target.get("targets", {}).get("sdist", {}).get("exclude", [])
    if not isinstance(exclude, list) or not all(isinstance(e, str) for e in exclude):
        return None
    return exclude


def tracked_files(root: Path) -> list[str] | None:
    """Return every file `git` tracks at `root`, submodules recursed into.

    Args:
        root: the repository's root.

    Returns:
        The paths `git ls-files` prints, one per element, or None where
        git exited non-zero.
    """
    result = subprocess.run(  # noqa: S603
        [_GIT, "ls-files", "--cached", "--recurse-submodules"],
        cwd=root,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.splitlines()


def excluded_tracked_files(exclude: list[str], files: list[str]) -> list[str]:
    """Return which of `files` the gitignore-style `exclude` list matches.

    The same call check-sdist's own hatchling plugin makes
    (`check_sdist.backends._base.pathspec_filter`, via
    `check_sdist.backends.hatchling.HatchlingBackend.git_only_excludes`),
    against the tracked files that call silently drops from what
    check-sdist would otherwise report missing: a match here is exactly
    that drop.

    Args:
        exclude: the exclude list.
        files: the tracked files to check it against.

    Returns:
        The matching paths, sorted.
    """
    spec = pathspec.GitIgnoreSpec.from_lines(exclude)
    return sorted(f for f in files if spec.match_file(f))


def main() -> int:
    """Fail where the exclude list matches a tracked file `_DELIBERATE` omits.

    Returns:
        0 where the entries match exactly `_DELIBERATE` among the
        tracked files, 1 where one matches anything else, where a
        member of `_DELIBERATE` is matched by nothing, where
        `sdist_exclude_patterns` cannot read the list, or where
        `git ls-files` itself failed.
    """
    pyproject_toml = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    exclude = sdist_exclude_patterns(pyproject_toml)
    if exclude is None:
        print(
            "pyproject.toml is no TOML, or [tool.hatch.build.targets.sdist]'s"
            " exclude is not an array of strings: this check has no pattern"
            " set to match, which is why it fails rather than answering"
            " (btclib-org/btclib-secp256k1#655)",
            file=sys.stderr,
        )
        return 1

    files = tracked_files(_ROOT)
    if files is None:
        print("git ls-files --cached --recurse-submodules failed", file=sys.stderr)
        return 1

    matched = excluded_tracked_files(exclude, files)
    unintended = [path for path in matched if path not in _DELIBERATE]
    for path in unintended:
        print(
            f"{path} is tracked and matches"
            " [tool.hatch.build.targets.sdist]'s exclude list: check-sdist"
            " does not see it leave the sdist, its hatchling plugin reading"
            " that very list and subtracting what it matches from the"
            " tracked files it would otherwise report missing"
            " (btclib-org/btclib-secp256k1#655). A file that entry drops on"
            " purpose belongs in this check's own _DELIBERATE"
            " (btclib-org/btclib-secp256k1#770)",
            file=sys.stderr,
        )
    unmatched = [path for path in _DELIBERATE if path not in matched]
    for path in unmatched:
        print(
            f"{path} is named in this check's _DELIBERATE and"
            " [tool.hatch.build.targets.sdist]'s exclude list matches no"
            " such tracked file: an exemption for a drop that is not"
            " happening would let a later entry take that file out of the"
            " sdist unreported (btclib-org/btclib-secp256k1#770)",
            file=sys.stderr,
        )
    if unintended or unmatched:
        return 1

    print("only the deliberate sdist exclude entries match a tracked file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
