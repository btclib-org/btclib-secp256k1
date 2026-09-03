# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Every job that builds a distribution pins `SOURCE_DATE_EPOCH`.

A build that does not export it writes the clock of the moment into the
archive: `hatchling` falls back to a constant of its own, but the repair
a wheel build is followed by -- `auditwheel`, `delocate` -- takes the
timestamp of every member it writes from the variable, and from the
clock where there is none. So a job that builds a published file and
omits the export publishes a file no rebuild reproduces, and one that
builds a file under measurement and omits it measures a build the
release does not run.

Nothing makes a new job carry the step. The export is per job, and
another wheel job, or a matrix split in two, is written by copying a
neighbour that may not be one of these -- the drift
`tests/wheel_reproducibility_platforms_test.py` documents one axis over,
where a hand-typed copy of a matrix goes stale with nothing red. This
finds the job rather than trusting a list of them: it reads both
workflows, asks which of their jobs run a build frontend, and requires
the pin of each -- of the commands each job runs, its comments being
prose about a step and not the step.

The frontends it knows are the spellings this tree uses: `cibuildwheel`,
`python -m build`, `uv build`, and `check_wheel_reproducibility.py`,
which runs one of them itself. A job reaching a build another way --
`python3 -m build`, `uvx --from build`, a backend called directly -- is
not discovered, and `test_a_job_of_each_shape_was_read` is what turns a
pattern that has stopped matching red rather than silently exempt.

`test.yml` and `wheel-reproducibility.yml` are the two files, and
between them they hold every build whose bytes are published or
compared: `release.yml` builds nothing of its own and calls `test.yml`
for the files it uploads. A build elsewhere -- `deps-latest.yml` builds
a wheel to run the suite against unpinned dependencies -- is neither
published nor diffed, and pinning its timestamp would answer no question
asked of it.

Read with a regex rather than parsed, for the reason
`interpreters_test.py` gives: a workflow is yaml and no group here
carries a parser for it.
"""

import re
from pathlib import Path

_ROOT = Path(__file__).parents[1]
_WORKFLOWS = (
    ".github/workflows/test.yml",
    ".github/workflows/wheel-reproducibility.yml",
)

# where the jobs start: everything above is triggers and permissions,
# and the paths filter up there names one of the scripts the patterns
# below look for
_JOBS = re.compile(r"^jobs:\n", re.MULTILINE)
# a top-level job key -- two spaces of indent, a name, and nothing after
# the colon -- which is what tells one apart from every line of a job's
# own body, all of which carry at least one more level of indent
_JOB_KEY = re.compile(r"^  (?P<name>[\w-]+):\n", re.MULTILINE)
# comment lines, dropped before a body is asked anything: every job of
# test.yml names build-cibuildwheel in one, and a build named in prose
# is not a build run
_COMMENT = re.compile(r"^ *#.*\n", re.MULTILINE)
# the build frontends, each as the command it is written as. The
# lookbehind is what keeps `needs: [build-cibuildwheel]` from reading as
# an invocation of it; check_wheel_reproducibility.py counts because it
# runs a frontend itself
_BUILDS = re.compile(
    r"(?<![-\w])cibuildwheel\b|python -m build|uv build"
    r"|check_wheel_reproducibility\.py"
)
# and the one invocation of that script that builds nothing: it
# downloads the archives two images already built and diffs them
_COMPARES_ONLY = re.compile(r"--across-images")
# the step itself, the value included: what has to hold is not that
# something is exported but that it is the commit's own date, which is
# what a rebuild from a tag recovers
_PIN = re.compile(r"SOURCE_DATE_EPOCH=\$\(git log -1 --pretty=%ct\)")


def _jobs(text: str) -> dict[str, str]:
    """Return each job's own body, keyed by name."""
    start = _JOBS.search(text)
    assert start, "no jobs: key in this workflow"
    region = text[start.end() :]
    keys = list(_JOB_KEY.finditer(region))
    assert keys, "no job in this workflow, or not in the expected shape"
    ends = [key.start() for key in keys[1:]] + [len(region)]
    return {
        key["name"]: region[key.end() : end]
        for key, end in zip(keys, ends, strict=True)
    }


def _building_jobs() -> dict[str, str]:
    """Return the commands of both workflows' jobs that build.

    The comments go before anything is asked, and what is stored is what
    is left: a job's comments name the step and the command as readily
    as its `run:` does -- most of the pin steps point at the one that
    carries the reasoning -- so a check reading them would take a
    sentence about the step for the step.
    """
    building: dict[str, str] = {}
    for workflow in _WORKFLOWS:
        text = (_ROOT / workflow).read_text(encoding="utf-8")
        for name, body in _jobs(text).items():
            code = _COMMENT.sub("", body)
            if _BUILDS.search(code) and not _COMPARES_ONLY.search(code):
                building[f"{Path(workflow).name}'s {name}"] = code
    return building


_BUILDING = _building_jobs()


def test_a_job_of_each_shape_was_read() -> None:
    """One job per frontend is found, so the check below is not vacuous.

    A job renamed, a step reindented or a frontend invoked another way
    would leave the search with fewer jobs to ask about and every
    assertion still green. These are one job per pattern the reader
    matches on, so a pattern that has stopped matching is red here
    rather than a job silently exempt.
    """
    for job in (
        "test.yml's build-cibuildwheel",
        "test.yml's build-dynamic",
        "wheel-reproducibility.yml's rebuild",
        "wheel-reproducibility.yml's repaired",
    ):
        assert job in _BUILDING, f"{job} builds a distribution and was not read"


def test_the_comparison_job_is_not_read_as_a_build() -> None:
    """`across-images` compiles nothing, so nothing is asked of it."""
    assert "wheel-reproducibility.yml's across-images" not in _BUILDING, (
        "the job that downloads two images' wheels and diffs them reads as"
        " a build, so the check below asks it for a pin it has no build to"
        " pin"
    )


def test_every_building_job_pins_the_timestamp() -> None:
    """Each build exports the commit's date as `SOURCE_DATE_EPOCH`."""
    unpinned = [name for name, code in _BUILDING.items() if not _PIN.search(code)]
    assert not unpinned, (
        f"{', '.join(unpinned)} builds a distribution without pinning"
        " SOURCE_DATE_EPOCH to the commit date: the archive then carries"
        " the clock of the moment it was built, and no rebuild of it"
        " returns the same bytes"
    )
