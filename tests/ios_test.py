# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""What the suite needs that the iOS simulator's test app does not give.

cibuildwheel runs this suite in the iOS simulator, in a test app that
holds the installed wheel and the paths `[tool.cibuildwheel.ios]`'s
`test-sources` names. The test below holds that list to every top-level
path `git ls-files` lists but those the sdist leaves out on purpose,
which `_DELIBERATE` in `.github/scripts/check_sdist_exclude.py` names:
cibuildwheel refuses a `test-sources` path the tree it builds from lacks,
and that tree can be the sdist.

What iOS refuses whatever the app holds has a mark of its own below. A
test that runs on iOS and needs it carries that mark, which skips it
where `sys.platform` is `ios` and nowhere else.
"""

import importlib.util
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).parents[1]
# resolved once, as symbols_test.py's own _GIT is
_GIT = shutil.which("git") or "git"
_SDIST_CHECK = _ROOT / ".github" / "scripts" / "check_sdist_exclude.py"

# CPython's subprocess refuses to start a process where sys.platform is
# "ios": `_can_fork_exec`, in its Lib/subprocess.py
STARTS_A_PROCESS = pytest.mark.skipif(
    sys.platform == "ios", reason="starts a process, which iOS refuses"
)

# iOS refuses the memory, both writable and executable, that
# `ffi.callback` allocates: `ILLEGAL_CALLBACK_DECLARATION`, in
# scripts/cffi_build.py, says how the static extension does without it.
# The zkp subpackage's context makes one, so a test that builds that
# context through a stand-in carries this mark too
MAKES_AN_FFI_CALLBACK = pytest.mark.skipif(
    sys.platform == "ios", reason="makes an ffi.callback, which iOS refuses"
)


def _left_out_of_the_sdist() -> set[str]:
    """Return the tracked files the sdist leaves out on purpose.

    A file below the top level is in no set of top-level paths, so
    subtracting it leaves its directory in, as the sdist does.

    Returns:
        The check's own `_DELIBERATE`.
    """
    spec = importlib.util.spec_from_file_location("check_sdist_exclude", _SDIST_CHECK)
    assert spec is not None
    assert spec.loader is not None
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    return set(check._DELIBERATE)


@STARTS_A_PROCESS
@pytest.mark.skipif(
    not (_ROOT / ".git").exists(),
    reason="this tree is not a git checkout, as an unpacked sdist is not one",
)
def test_the_test_app_holds_what_a_checkout_and_the_sdist_both_hold() -> None:
    """`test-sources` names each top-level path a build of either finds.

    The independent side is git's own listing of the tree, less what the
    sdist check names as left out on purpose.
    """
    with (_ROOT / "pyproject.toml").open("rb") as file:
        sources = set(tomllib.load(file)["tool"]["cibuildwheel"]["ios"]["test-sources"])
    listed = subprocess.run(  # noqa: S603
        [_GIT, "-C", str(_ROOT), "ls-files"],
        capture_output=True,
        check=True,
        encoding="utf-8",
    ).stdout.splitlines()
    held = {path.split("/")[0] for path in listed} - _left_out_of_the_sdist()
    assert sources == held, (
        f"missing from test-sources: {sorted(held - sources)};"
        f" not held by both: {sorted(sources - held)}"
    )
