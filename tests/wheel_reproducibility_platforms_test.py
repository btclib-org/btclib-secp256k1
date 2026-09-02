# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""`wheel-reproducibility.yml` builds on the platforms the release does.

`tests/interpreters_test.py` is the same shape one axis over: three
sentinels each carry their own copy of an interpreter list, nothing
compares them, and the three drift in the direction that is hardest to
notice. Here it is one pair rather than three, and one platform axis
rather than an interpreter one -- `wheel-reproducibility.yml`'s own
`os:` list is a hand-typed copy of `build-cibuildwheel`'s in `test.yml`,
kept in sync by a comment in each file rather than by anything that
fails when the two disagree. This is that check.

GitHub Actions gives one workflow no way to read another's
`strategy.matrix` short of `workflow_call`, which neither file uses --
so the two lists are not read from one another at runtime, and never
can be without wiring the sentinel into the gate, which
`wheel-reproducibility.yml`'s own header explains is not wanted. What is
checkable is that the two texts agree, which is what this asks on every
run of the suite instead of on whoever next edits one of the two files
and forgets the other.

Read with a regex rather than parsed, for the same reason
`interpreters_test.py` gives: a workflow is yaml and no group here
carries a parser for it.
"""

import re
from pathlib import Path

_ROOT = Path(__file__).parents[1]
_GATE = (_ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
_SENTINEL = (_ROOT / ".github/workflows/wheel-reproducibility.yml").read_text(
    encoding="utf-8"
)

# a top-level job key: two spaces of indent and then a non-space, which
# is what tells one apart from every deeper line in its own body -- a
# step, a matrix entry, a comment -- all of which carry at least one
# more level of indent and so a space in the third column instead
_NEXT_JOB = re.compile(r"^  \S.*:\n", re.MULTILINE)
# the matrix `os:` list this repository writes one entry per line, at
# eight spaces with each entry indented two further -- the shape both
# files use for this particular list, distinct from the bracketed
# `os: [a, b]` a few other jobs in test.yml carry for theirs
_OS_LIST = re.compile(r"^        os:\n(?P<block>(?:^          - \S+\n)+)", re.MULTILINE)


def _job_body(text: str, name: str) -> str:
    """Return one top-level job's own text, the next job's key excluded."""
    start = re.search(rf"^  {re.escape(name)}:\n", text, re.MULTILINE)
    assert start, f"no {name}: job in this workflow"
    rest = text[start.end() :]
    end = _NEXT_JOB.search(rest)
    return rest[: end.start()] if end else rest


def _os_list(body: str) -> tuple[str, ...]:
    """Return the `os:` list a job body names, in order."""
    match = _OS_LIST.search(body)
    assert match, "no os: list in this job, or not in the expected shape"
    return tuple(line.strip().lstrip("- ") for line in match["block"].splitlines())


_GATE_PLATFORMS = _os_list(_job_body(_GATE, "build-cibuildwheel"))
_SENTINEL_PLATFORMS = _os_list(_job_body(_SENTINEL, "rebuild"))


def test_the_two_platform_lists_were_read() -> None:
    """Each list is non-empty, so the comparison below is not vacuous.

    A job renamed, a matrix reindented, or the `os:` list rewritten in
    the bracketed shape would each leave one of these empty and the
    equality check trivially true.
    """
    assert _GATE_PLATFORMS, "test.yml's build-cibuildwheel names no platform"
    assert _SENTINEL_PLATFORMS, "wheel-reproducibility.yml's rebuild names none"


def test_wheel_reproducibility_runs_on_every_wheel_platform() -> None:
    """The sentinel's matrix is exactly the gate's wheel-building one.

    Order included: the two are read side by side when one goes red, and
    a list in a different order is one a reader has to diff rather than
    compare.
    """
    assert _SENTINEL_PLATFORMS == _GATE_PLATFORMS, (
        f"wheel-reproducibility.yml runs on {', '.join(_SENTINEL_PLATFORMS)}"
        f" where build-cibuildwheel builds on {', '.join(_GATE_PLATFORMS)}:"
        " a platform added to one and forgotten in the other is a wheel"
        " this measurement never reaches, or a platform it claims to and"
        " does not build"
    )
