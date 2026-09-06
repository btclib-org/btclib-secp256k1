# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Every submodule .gitmodules names is checked out, or check-sdist is blind.

check-sdist (henryiii/check-sdist) compares the sdist hatchling builds
against `git ls-files --cached --recurse-submodules`. That flag has
nowhere to recurse into when a submodule is not checked out, so its own
answer silently drops the submodule rather than erroring on it -- and
the sdist hatchling builds is equally empty there, so the two agree and
"SDist matches git" is printed with a whole vendored tree missing from
both sides at once (btclib-org/btclib-secp256k1#612). Nothing here is
check-sdist's own bug in the ordinary sense: it is told to trust git's
answer, and git gave a self-consistent one for the tree it was asked
about. But the guarantee the hook exists to give -- that the sdist a
user installs carries what this repository ships -- does not hold the
moment a submodule is not checked out.

This hook is what says so, ahead of check-sdist in
.pre-commit-config.yaml: `.gitmodules` names every submodule this
repository has, parsed directly rather than asked of `git config` so
that reading it needs no repository context and cannot be confused by a
git hook's inherited GIT_DIR the way a `-C` call could be
(check_submodule_pin.py's own module docstring has that hazard's full
reasoning). Each path is then checked the same way
check_submodule_pin.py's `_checked_out` does: whether it has a `.git` of
its own, not whether `git -C <path>` answers anything -- `-C` does not
stop git's own upward directory discovery when `<path>` has no `.git`,
so a filesystem check first is what keeps a later git call, in either
script, from silently walking up into this wrapper repository instead.

`always_run`, for the reason submodule-pin already is: the state this
checks -- is a submodule's working tree present -- is independent of
which files a commit touches, so a `files` pattern could never be the
right trigger for it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

# .gitmodules is git's own config format: one "path = ..." line per
# submodule, indented under its "[submodule ...]" header. A plain regex
# reads every one of them without asking git to parse the file, the same
# choice check_submodule_pin.py makes for the release link in README.md
_PATH = re.compile(r"^\s*path\s*=\s*(\S+)\s*$", re.MULTILINE)


def submodule_paths(gitmodules: str) -> list[str]:
    """Return every submodule path .gitmodules names.

    Args:
        gitmodules: the text of .gitmodules.

    Returns:
        The paths, in the order .gitmodules lists them. Empty where the
        text names none.
    """
    return _PATH.findall(gitmodules)


def checked_out(path: Path) -> bool:
    """Whether a submodule has a `.git` of its own under `path`.

    Args:
        path: the submodule's working directory.

    Returns:
        True where `path/.git` exists, False where the submodule was
        never initialized (or `path` itself does not exist).
    """
    return (path / ".git").exists()


def main() -> int:
    """Fail where a submodule .gitmodules names is not checked out.

    Returns:
        0 where every submodule is checked out, 1 where any is not, or
        where .gitmodules names none at all -- a repository with
        submodules that lists none is a check that cannot ask its
        question, the same failure shape check_submodule_pin.py's
        `main` gives a README naming no release.
    """
    gitmodules = _ROOT / ".gitmodules"
    if not gitmodules.exists():
        print(".gitmodules does not exist", file=sys.stderr)
        return 1

    paths = submodule_paths(gitmodules.read_text(encoding="utf-8"))
    if not paths:
        print(".gitmodules names no submodule", file=sys.stderr)
        return 1

    missing = [path for path in paths if not checked_out(_ROOT / path)]
    if missing:
        for path in missing:
            print(
                f"{path} is not checked out: check-sdist's comparison against"
                " git silently drops an uninitialized submodule instead of"
                " failing on it (btclib-org/btclib-secp256k1#612), so the"
                f" sdist it builds would ship without {path}'s content and the"
                " hook would still say the sdist matches git."
                f" git submodule update --init {path}",
                file=sys.stderr,
            )
        return 1

    print("every submodule .gitmodules names is checked out")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
