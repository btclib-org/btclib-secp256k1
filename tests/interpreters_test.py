# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""The interpreters this package claims are the ones it runs on.

One fact, declared three times: `requires-python` is the floor,
`Programming Language :: Python :: X.Y` is what PyPI shows whoever is
choosing the package, and the platform sentinels' own lists are what
actually runs. Nothing compared them, and the three drift in the
direction that is hardest to notice -- a classifier left behind when a
floor moves is a package advertising an interpreter its suite never
touches, and the person it misleads is not reading this repository.

The sentinels are where the interpreter set lives because that is where
the suite meets every interpreter: the merge gate runs one cell, on the
version `.python-version` pins, and `os-ubuntu.yml`'s header says why. Each
of the three carries the list in full, and each of their comments says
the other two carry the same one, so the list is read per file and the
three are required to agree: a version added to one and forgotten in
another is a difference between platforms, which is the one thing a
platform sweep is arranged so as not to have.

The organization standard's rule is that a library covers every Python
that is not out of support, so all three move together twice around each
October: one version leaves support as another is released. This module
does not know that calendar and does not try to -- python.org keeps it,
and a test that hard-coded a date would be one more thing to move. What
it holds is the weaker and checkable claim: whatever the three say, they
say the same thing.

Read with a regex rather than parsed. `tomllib` arrives in 3.11 and the
floor here is 3.10, which is the reason `copyright_test.py` reads
pyproject.toml the same way; a workflow is yaml and no group here
carries a parser for it.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parents[1]
_PYPROJECT = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
_SENTINELS = ("os-ubuntu.yml", "os-macos.yml", "os-windows.yml")
_WORKFLOWS = {
    name: (_ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
    for name in _SENTINELS
}

# "3.10" out of `requires-python = ">=3.10"`, the floor and nothing else:
# an upper bound is not declared here and would be a different claim
_FLOOR = re.compile(r'^requires-python = ">=(?P<version>3\.\d+)"', re.MULTILINE)
# the per-version classifiers, not `:: 3` or `:: 3 :: Only`, which say
# something about the major version rather than about an interpreter
_CLASSIFIER = re.compile(
    r'^    "Programming Language :: Python :: (?P<version>3\.\d+)",$', re.MULTILINE
)
_PYPY_CLASSIFIER = "Programming Language :: Python :: Implementation :: PyPy"
# PyPI's free-threading classifiers, the bare one and its maturity levels
# alike: each is a claim about the code under a free-threaded build, and
# which is claimed is not this module's question
_FREE_THREADING_CLASSIFIER = re.compile(
    r'^    "Programming Language :: Python :: Free Threading(?: :: .+)?",$',
    re.MULTILINE,
)
# the `python-version` list of a sentinel's suite matrix. The key has to
# be alone on its line, which is what leaves out the `exclude:` entries
# below it: those spell the same key with a value beside it, and an
# excluded cell is an interpreter that cannot run on one image rather
# than one this package does not claim
_PYTHONS = re.compile(
    r'^        python-version:\n(?P<block>(?:^          - "\S+"\n)+)', re.MULTILINE
)
# the shape a caller of the sentinels' own reusable-os-suite.yml will
# carry, once one of them becomes a caller (btclib-org/.github#35). No
# such caller exists yet -- this is derived, not read off a landed file:
# reusable-deps-oldest.yml's own five callers already establish the
# `with:` indent and the quoting for one interpreter,
# `python-version: "3.10"`, and a `workflow_call` input can only be a
# string, so the list a caller will pass arrives JSON-encoded inside
# one -- `python-versions: '["3.10", "3.11"]'`. Read alongside
# `_PYTHONS` rather than instead of it: every sentinel still declares
# the block sequence above until that merge lands, and a pattern that
# read only the caller shape would turn the suite red today
# (btclib-org/.github#1119)
_PYTHONS_CALLER = re.compile(
    r"^      python-versions: '(?P<block>\[.*?\])'$", re.MULTILINE
)
# the merge gate, and inside it the jobs a landing waits on: the
# aggregate's own `needs:` closure, which is what section 3 of the
# organization standard asks for. It declares a free-threading classifier
# where the gate exercises that build, a gate being what refuses the
# landing that breaks it, so an interpreter named only by a job nothing
# waits on is the "it passed somewhere" that section refuses. Reading the
# file whole is the alternative it names as rejected, and it answers the
# same here, every job of this workflow sitting in that closure; what it
# costs is the day one is moved out, which the file read cannot see
_GATE = _ROOT / ".github/workflows/test.yml"
# the aggregate, by the name a required context is keyed on, which is a
# job's `name:` and not its key
_AGGREGATE = "test: every job passed"
# comments go first, so that a sentence about a sentinel's free-threaded
# cell does not read as the gate running one
_COMMENT = re.compile(r"(?:^|\s)#.*$", re.MULTILINE)
# a job names in its own text the interpreter it runs, as
# `python-version: "3.14"` or `--python 3.14`, so a job's interpreters
# are read as tokens off that text rather than out of a matrix block:
# the gate's own header says it is one suite cell rather than a matrix. A
# free-threaded build named that way is a "3.14t" of the same shape. What
# a job leaves to cibuildwheel is outside this read: those identifiers
# come from `requires-python`, `enable` and `skip`, spelled `cp314t`
# rather than as a version in any file here --
# `_cibuildwheel_free_threaded_interpreters` below is what reads those,
# for whichever job in the closure hands them to cibuildwheel instead of
# writing them out itself
_INTERPRETER = re.compile(r"\b3\.\d+t?\b")
# a cibuildwheel identifier for a free-threaded build, e.g.
# "cp314t-manylinux_aarch64": the digit after "cp" is the major version,
# always "3" for every interpreter this package still supports, the run
# of digits after it the minor, and the "t" the free-threaded ABI tag
# `--print-build-identifiers` spells and no workflow file does
_CIBW_FREE_THREADED = re.compile(r"^cp3(?P<minor>\d+)t-", re.MULTILINE)
# the floor of pyproject.toml's `test` group entry for cibuildwheel, which
# is the one entry carrying a marker after its version: `build` has an
# entry of its own with none, and that one is not this test's to read. It
# is read out of the entry rather than restated, so that the floor is
# written once, and `_require_cibuildwheel` holds the installed release to it
_CIBW_FLOOR = re.compile(r'^    "cibuildwheel>=(?P<version>[0-9.]+);', re.MULTILINE)
# cibuildwheel's own vocabulary for --platform, not the runner images
# build-cibuildwheel's matrix names: ubuntu-latest and ubuntu-24.04-arm
# are both "linux", macos-26-intel and macos-latest "macos", windows-latest
# and windows-11-arm "windows". Asked once per platform rather than once,
# because [tool.cibuildwheel]'s `skip` can name one platform's identifier
# and not another's -- today's `pp*-win* cp310-win_arm64` already does
_CIBW_PLATFORMS = ("linux", "macos", "windows")
# `jobs:` and everything under it. The keys of `on:` sit at the indent a
# job key does, so a pattern that did not cut here would offer
# `pull_request` to the closure below as a job of the workflow
_JOBS = re.compile(r"^jobs:\n(?P<block>.*)\Z", re.MULTILINE | re.DOTALL)
# a job key at the one indent `jobs:` gives them, and everything it
# indents under. The block runs a space below a job attribute's own
# indent and takes a whitespace-only line, which is the slack that
# absorbs what dropping a comment leaves: `_COMMENT` takes the
# whitespace before the `#` with it, so a comment on a line of its own
# arrives here one space short of where it was written
_JOB = re.compile(
    r"^  (?P<key>[a-z0-9_-]+):\n(?P<block>(?:^ {3,}.*\n|^ *\n)*)", re.MULTILINE
)
# a job's own `name:`, at the indent its attributes take: a step's name
# is deeper and is not matched here. A block scalar reads as `>-`, which
# is no aggregate's name and needs no excluding
_NAME = re.compile(r'^    name: "?(?P<name>[^"\n]*?)"?$', re.MULTILINE)
# `needs:` in each of the three shapes GitHub takes -- one job after the
# key, a flow list there, and a block list under it -- read as whatever
# follows the key on its own line plus the items below it. A reader blind
# to the block shape answers a closure short of whatever sits behind an
# edge written that way. Where the jobs the narrowing keeps still name
# an interpreter it answers short in silence, the biconditional below
# passing on a gate it has not read; where the narrowing leaves the
# aggregate alone, the aggregate's own job names none and the `the jobs
# test.yml's gate waits on name no interpreter` assertion ahead of that
# biconditional fires instead (btclib-org/.github#1031).
#
# The run of items takes a comment line and a blank one as well, and an
# item's own trailing comment with it: a whole-line comment among the
# items, a blank line between two of them and a `#` after an item are one
# thing to a yaml reader, and a run of adjacent item lines ends at each of
# them and drops every item below. A copy whose `_jobs` strips comments
# before the job blocks are read meets whitespace where one that leaves
# them meets the comment itself; the run takes both, and one spelling
# answers for the organization's copies of this module rather than for
# this tree (btclib-org/.github#1038).
#
# What the run must not take is a step: `steps:` entries sit at the item
# indent, and `      - name: Setup uv` is kept out by an item being the
# whole line up to its comment.
#
# What it still does not read, it drops without saying so, and the cases
# are named because they are not equally bad. A flow list wrapped across
# lines keeps only what sat on the key line: nothing where the bracket
# stands alone, the first entry alone where it does not. A flow list
# exploded under the key, and a block list at any other indent, keep none
# of it.
_NEEDS = re.compile(
    r"^    needs:(?P<inline>[^#\n]*)(?:#[^\n]*)?\n"
    r"(?P<items>(?:^      - \S+[ \t]*(?:#[^\n]*)?\n|^[ \t]*(?:#[^\n]*)?\n)*)",
    re.MULTILINE,
)
# one item of the block list above, the key picked off a line the run has
# already read as an item
_ITEM = re.compile(r"^      - (?P<key>\S+)", re.MULTILINE)
# the job that hands the build to cibuildwheel, whose `CIBW_BUILD` is what
# narrows the interpreters a pull request builds there
_BUILD_JOB = "build-cibuildwheel"
# a cibuildwheel setting named anywhere in the job's own text. The read
# below reproduces one, `CIBW_BUILD`, on top of what `[tool.cibuildwheel]`
# configures, so a second name -- `CIBW_SKIP`, `CIBW_ENABLE` -- is a job
# whose selection it cannot reproduce
_CIBW_VARIABLE = re.compile(r"CIBW_\w+")
# what a `name:` says is prose about the job or a step, and a name that
# mentions a setting sets none. It is found by its indent and its key, at
# the places a name sits: the job's own at four spaces, a step's on its
# dash line, and a step's beside its other keys at eight spaces, where
# `_STEP_KEY` reads them. The key survives, and the value goes: the dash line's
# `- ` is what `_STEP` splits the steps at, so a line dropped whole would
# join the step to the one above it. A value folded over further lines is
# not reached, and a setting named on the second of them reads as a second
_NAME_VALUE = re.compile(r"^(?P<key>(?: {4}| {8}| {6}- )name:).*$", re.MULTILINE)
# a step that runs cibuildwheel names it, the command or the action alike;
# what a `name:` says of it is gone by the time this is asked
_RUNS_CIBUILDWHEEL = re.compile(r"\bcibuildwheel\b")
# each step: a step's `- ` sits two spaces left of its keys, which
# `_STEP_KEY` reads at their own indent and no deeper: `shell: bash` under
# an `env:` or a `with:` is that key's input and not the step's
_STEP = re.compile(r"^      - ", re.MULTILINE)
_STEP_KEY = re.compile(r"^ {8}(?P<key>[\w-]+):[ \t]*(?P<value>.*)$", re.MULTILINE)
# the one condition the read accepts, spelled as `test.yml` spells it
_ONLY_A_PULL_REQUEST = "github.event_name == 'pull_request'"
# the one command the read accepts: a double-quoted literal, so that the
# value is what the file says rather than what a shell makes of it, and at
# least one pattern in it, so that it is not the empty string
_SETS_CIBW_BUILD = re.compile(
    r'echo "CIBW_BUILD=(?P<value>[^"$`\\\s][^"$`\\]*)" >> "\$GITHUB_ENV"'
)


def _versions(pattern: re.Pattern[str], text: str) -> tuple[str, ...]:
    """Return every `version` group `pattern` finds, in order."""
    return tuple(m["version"] for m in pattern.finditer(text))


def _jobs() -> dict[str, str]:
    """Return each job of the merge gate against its text, comments dropped."""
    jobs = _JOBS.search(_COMMENT.sub("", _GATE.read_text(encoding="utf-8")))
    assert jobs, f"{_GATE.name} declares no jobs"
    return {match["key"]: match["block"] for match in _JOB.finditer(jobs["block"])}


def _waits_on(block: str) -> list[str]:
    """Return the jobs one job's `needs:` names, in whichever shape."""
    needs = _NEEDS.search(block)
    if not needs:
        return []
    listed = needs["inline"].strip("[] ").replace(",", " ").split()
    return listed + _ITEM.findall(needs["items"])


def _closure(jobs: dict[str, str], key: str) -> set[str]:
    """Return `key` and every job it waits on, however deep."""
    found = {key}
    pending = [key]
    while pending:
        for name in _waits_on(jobs[pending.pop()]):
            if name not in found:
                found.add(name)
                pending.append(name)
    return found


def _require_cibuildwheel() -> None:
    """Skip the test running this unless a cibuildwheel that can answer is here.

    One that can answer is one at `_CIBW_FLOOR` or newer: an older release
    prints no free-threaded identifier for `[tool.cibuildwheel]`'s
    configuration, so its answer is "none" whatever the gate builds, which
    reads as a gate that runs no free-threaded interpreter. Where there is
    none at all, or only an older one, the test is skipped rather than
    answered from this file's text, which is the read that cannot see it.
    """
    floor = _CIBW_FLOOR.search(_PYPROJECT)
    assert floor, "pyproject.toml's `test` group names no floor for cibuildwheel"
    pytest.importorskip(
        "cibuildwheel",
        minversion=floor["version"],
        reason=(
            "cibuildwheel is not installed here, and it is what lists the"
            " free-threaded identifiers the gate builds: the `test` group"
            " carries it from Python 3.11, and the wheel test and the sdist"
            " test do not carry it"
        ),
    )


def _child_environment() -> dict[str, str]:
    """Return this process's environment without cibuildwheel's own settings.

    Every `CIBW_*` variable overrides `[tool.cibuildwheel]`, and
    `--print-build-identifiers` prints what the override selects: with
    `CIBW_BUILD` set to `cp310-*` it prints cp310's. What this asks is
    what the tree configures, so the caller's settings do not reach the
    child.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("CIBW_")}


def _print_build_identifiers(
    platform: str, environ: dict[str, str] | None = None
) -> str:
    """Return the output of `--print-build-identifiers` for `platform`.

    Under `_child_environment()` unless `environ` names another: the
    caller's own settings, for the test that they do not reach the default
    answer, or `_child_environment()` with a selection's `CIBW_BUILD` added,
    for `_platforms_without_free_threaded`. A non-zero exit fails the test
    with cibuildwheel's own stderr, which is where it says what it refused.
    """
    _require_cibuildwheel()
    printed = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "cibuildwheel",
            "--print-build-identifiers",
            "--platform",
            platform,
        ],
        cwd=_ROOT,
        env=_child_environment() if environ is None else environ,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    if printed.returncode:
        pytest.fail(
            f"cibuildwheel --platform {platform} exited {printed.returncode}:\n"
            f"{printed.stderr}",
            pytrace=False,
        )
    return printed.stdout


def _cibuildwheel_free_threaded_interpreters() -> tuple[str, ...]:
    """Ask cibuildwheel itself which free-threaded identifiers it builds.

    `requires-python`, `enable` and `skip` in `[tool.cibuildwheel]` decide
    the identifiers cibuildwheel actually builds, and a release of
    cibuildwheel can move which interpreters are free-threaded by default
    with nothing in this tree changing -- so this asks it, once per
    platform in `_CIBW_PLATFORMS`, rather than tracking that migration in
    this file's own text the way `_INTERPRETER` tracks a job's.
    """
    minors: set[str] = set()
    for platform in _CIBW_PLATFORMS:
        printed = _print_build_identifiers(platform)
        minors.update(m["minor"] for m in _CIBW_FREE_THREADED.finditer(printed))
    return tuple(sorted(f"3.{minor}t" for minor in minors))


def _gate_closure(jobs: dict[str, str]) -> set[str]:
    """Return the required check's aggregate and every job it waits on."""
    keyed = {
        match["name"]: key
        for key, block in jobs.items()
        for match in _NAME.finditer(block)
    }
    assert _AGGREGATE in keyed, (
        f"{_GATE.name} carries no job named {_AGGREGATE!r}, which is the"
        " required check the closure is read from"
    )
    return _closure(jobs, keyed[_AGGREGATE])


def _gate_interpreters() -> tuple[str, ...]:
    """Return every interpreter the jobs the merge gate waits on name.

    Text first, for every job in the closure; then, for whichever of
    those jobs hands its own build to cibuildwheel, the free-threaded
    identifiers that tool would build, which `_INTERPRETER` cannot see.
    That second read skips the calling test where no cibuildwheel that can
    answer is installed (`_require_cibuildwheel`). The membership test is
    a full comprehension over the closure rather than `any` stopping at
    the first match, so every job's text is visited regardless of where in
    `closure`'s (unordered) iteration the one that mentions cibuildwheel
    falls -- an `any` that stops early would leave the branch it does not
    reach uncovered on a run where that job happens to be visited first.
    """
    jobs = _jobs()
    closure = _gate_closure(jobs)
    found = {v for key in closure for v in _INTERPRETER.findall(jobs[key])}
    cibuildwheel_jobs = [key for key in closure if "cibuildwheel" in jobs[key]]
    if cibuildwheel_jobs:
        found.update(_cibuildwheel_free_threaded_interpreters())
    return tuple(sorted(found))


def _pull_request_selection(job: str) -> str:
    """Return the `CIBW_BUILD` a pull request gives `job`, or "" if not read.

    The step is found by what it writes and not by what it is called: the
    `name:` values are dropped first (`_NAME_VALUE`), so a step named after
    the setting it sets is read, and a name that mentions another setting
    is not a second one. The value comes back where what is left of the job
    names exactly one `CIBW_` setting, `CIBW_BUILD`, and it sits in a step,
    a `- ` item at the indent `test.yml` writes its steps at, that carries
    these three keys, in any order, among whatever others:

    - `if` is `github.event_name == 'pull_request'` and nothing more;
    - `shell` is `bash`, the default on the two Windows images being
      PowerShell, where `"$GITHUB_ENV"` is not the variable and the step
      selects nothing;
    - `run` is one line, `echo "CIBW_BUILD=<patterns>" >> "$GITHUB_ENV"`,
      with the patterns a literal that expands nothing.

    The step comes before the first one that names cibuildwheel, since
    `$GITHUB_ENV` reaches the steps after the one that writes it and no
    other; a job with no step that names it selects nothing either.

    Everything else reads as "": a second `CIBW_` name outside a `name:`,
    whether a job's `env:`, another step or another variable; a condition
    that is compound, another event's or absent; a `shell` that is not
    `bash`; a `run` that is a block scalar, writes to another file, expands
    a variable, holds a backtick or a backslash, sets an empty value, or
    has text before or after the one command; a step that comes after the
    one that builds, or a job that has none. A step restructured out of
    these shapes is then nothing rather than a guess, and
    `test_the_pull_request_selection_was_read` is what fails on the
    nothing. `job` has its comments dropped already, as `_jobs` returns it.

    What is not read is the arguments of the command that runs
    cibuildwheel, which can narrow a selection as well.
    """
    code = _NAME_VALUE.sub(r"\g<key>", job)
    named = _CIBW_VARIABLE.findall(code)
    steps = _STEP.split(code)[1:]
    holding = [i for i, step in enumerate(steps) if _CIBW_VARIABLE.search(step)]
    building = [i for i, step in enumerate(steps) if _RUNS_CIBUILDWHEEL.search(step)]
    if len(named) != 1 or not holding or not building or min(building) <= holding[0]:
        return ""
    keys = dict(_STEP_KEY.findall(" " * 8 + steps[holding[0]]))
    written = _SETS_CIBW_BUILD.fullmatch(keys.get("run", ""))
    if (
        written is None
        or keys.get("if") != _ONLY_A_PULL_REQUEST
        or keys.get("shell") != "bash"
    ):
        return ""
    return written["value"]


def _gate_selection() -> str:
    """Return what `_pull_request_selection` reads of the gate's build job."""
    return _pull_request_selection(_jobs().get(_BUILD_JOB, ""))


def _platforms_without_free_threaded(selection: str) -> list[str]:
    """Return the platforms where `selection` builds no free-threaded wheel.

    Empty where the free-threading classifier is not declared: nothing
    is then claimed about that build, and cibuildwheel is not asked.
    Otherwise it is asked once per platform in `_CIBW_PLATFORMS`, with
    `selection` as `CIBW_BUILD` on top of what `_child_environment` leaves
    of the caller's, which is the environment the step gives the job and no
    more. What cibuildwheel prints is the identifiers `[tool.cibuildwheel]`
    configures that `selection` keeps: a pattern naming one the
    configuration skips keeps nothing.
    """
    if not _FREE_THREADING_CLASSIFIER.search(_PYPROJECT):
        return []
    environ = {**_child_environment(), "CIBW_BUILD": selection}
    return [
        platform
        for platform in _CIBW_PLATFORMS
        if not _CIBW_FREE_THREADED.search(_print_build_identifiers(platform, environ))
    ]


def _matrix(text: str) -> tuple[str, ...]:
    """Return the interpreters one sentinel's suite matrix names, in order.

    `_PYTHONS`'s block sequence, still what every sentinel writes today,
    and `_PYTHONS_CALLER`'s JSON-encoded list, the shape a caller of
    `reusable-os-suite.yml` will carry once one exists
    (btclib-org/.github#1119) -- both read here so a tree on either side
    of that migration is read correctly. A sentinel carries one shape or
    the other, never both, so the two are simply concatenated.
    """
    block = tuple(
        line.strip().lstrip("- ").strip('"')
        for match in _PYTHONS.finditer(text)
        for line in match["block"].splitlines()
    )
    caller = tuple(
        version
        for match in _PYTHONS_CALLER.finditer(text)
        for version in re.findall(r'"(\S+?)"', match["block"])
    )
    return block + caller


_CLASSIFIED = _versions(_CLASSIFIER, _PYPROJECT)
_DECLARED = {name: _matrix(text) for name, text in _WORKFLOWS.items()}
# the list the classifier checks below quantify over: one file's, which
# the equality test makes all three. Any other way of combining them
# reports a version some sentinel carries, and the question those checks
# ask is about a version every sentinel runs
_MATRIX = _DECLARED[_SENTINELS[0]]
# the free-threaded build and PyPy are the same interpreter version as
# far as a classifier is concerned: "3.14t" is CPython 3.14, and
# "pypy-3.11" is what the PyPy classifier covers rather than a version
# of its own
_CPYTHON = tuple(sorted({v.rstrip("t") for v in _MATRIX if not v.startswith("pypy")}))


def test_the_three_declarations_were_read() -> None:
    """Each pattern found something, so the checks below quantify over it.

    A key renamed, a classifier reindented, a sentinel's matrix
    reindented: each would leave one of these empty and every comparison
    below trivially true.
    """
    assert _FLOOR.search(_PYPROJECT), "pyproject.toml declares no requires-python"
    assert _CLASSIFIED, "pyproject.toml declares no per-version Python classifier"
    unread = [name for name, declared in _DECLARED.items() if not declared]
    assert not unread, (
        f"declares no python-version list: {', '.join(unread)}."
        " A key renamed or a matrix reindented reads as an empty list"
    )


def test_the_three_sentinels_carry_the_same_interpreters() -> None:
    """The platform is the only thing that differs between the three.

    Each sentinel's matrix comment says the other two carry the same
    list; this is that sentence checked. Order included: the three are
    read side by side when one of them goes red, and a list in a
    different order is one a reader has to diff rather than compare.
    """
    reference, *others = _SENTINELS
    for name in others:
        assert _DECLARED[name] == _DECLARED[reference], (
            f"{name} runs {', '.join(_DECLARED[name])} where {reference} runs"
            f" {', '.join(_DECLARED[reference])}: an interpreter covered on"
            " one platform and not another is a gap no red cell reports"
        )


def test_the_floor_is_the_lowest_classifier() -> None:
    """`requires-python` and the classifiers name the same oldest Python."""
    floor = _FLOOR.search(_PYPROJECT)
    assert floor, "pyproject.toml declares no requires-python"
    lowest = min(_CLASSIFIED, key=lambda v: tuple(int(p) for p in v.split(".")))
    assert floor["version"] == lowest, (
        f"requires-python is >={floor['version']} and the lowest classifier"
        f" is {lowest}: one of the two was moved and the other was not"
    )


def test_every_classified_interpreter_is_in_the_matrix() -> None:
    """A version PyPI advertises is a version the suite runs."""
    unrun = [v for v in _CLASSIFIED if v not in _CPYTHON]
    assert not unrun, (
        f"classified and run by no platform sentinel: {', '.join(unrun)}."
        " PyPI shows a classifier to whoever is choosing this package"
    )


def test_every_matrix_interpreter_is_classified() -> None:
    """A version the suite runs is a version PyPI advertises."""
    unclassified = [v for v in _CPYTHON if v not in _CLASSIFIED]
    assert not unclassified, (
        f"run by a platform sentinel and not classified: {', '.join(unclassified)}"
    )


def test_pypy_is_classified_exactly_when_it_is_run() -> None:
    """The PyPy classifier is a claim about the matrix, not a decoration."""
    classified = _PYPY_CLASSIFIER in _PYPROJECT
    run = any(v.startswith("pypy") for v in _MATRIX)
    assert classified == run, (
        f"the PyPy classifier is {'present' if classified else 'absent'} and"
        f" the matrix {'runs' if run else 'does not run'} a PyPy interpreter"
    )


def test_free_threading_is_classified_exactly_when_the_gate_runs_it() -> None:
    """The free-threading classifier is a claim about the merge gate.

    The organization standard declares one where the gate exercises the
    free-threaded build: a gate refuses the landing that breaks that
    build, where a sentinel runs beside a landing and blocks nothing. So
    the second side here is the jobs the required check waits on and not
    `_MATRIX` -- the sentinels name "3.14t" as readily as the gate would,
    and a sentinel passing is the ground the standard declines.

    The aggregate's own job names no interpreter, so the assertion below
    is the `needs:` read's control as much as the pattern's: a read that
    matched nothing leaves the closure at that one job and this empty.

    The interpreter a job leaves to cibuildwheel to pick is spelled nowhere
    in `test.yml`'s own text, so `_gate_interpreters` asks cibuildwheel
    itself wherever a job in the closure calls it (#867). This test is
    skipped where none that can answer is installed, and is not answered
    from the file's text there.
    """
    gate = _gate_interpreters()
    assert gate, "the jobs test.yml's gate waits on name no interpreter"
    classified = bool(_FREE_THREADING_CLASSIFIER.search(_PYPROJECT))
    run = [v for v in gate if v.endswith("t")]
    assert classified == bool(run), (
        f"the free-threading classifier is {'present' if classified else 'absent'}"
        f" and the jobs test.yml's gate waits on name"
        f" {', '.join(run) or 'no free-threaded interpreter'}"
    )


def test_the_pull_request_selection_was_read() -> None:
    """The build job is one the gate waits on, and its selection was found.

    A step restructured out of the shapes `_pull_request_selection` accepts,
    a condition rewritten, a job renamed: each reads as nothing, and the
    test below then asks cibuildwheel about an empty `CIBW_BUILD`, which
    keeps every identifier the configuration lists, a free-threaded one
    included, and passes. This is what fails on the nothing. It is text
    alone and runs where the test below is skipped.
    """
    assert _BUILD_JOB in _gate_closure(_jobs()), (
        f"{_GATE.name}'s {_BUILD_JOB} is not among the jobs the required"
        " check waits on: what it builds on a pull request is not a gate"
    )
    assert _gate_selection(), (
        f"{_GATE.name}'s {_BUILD_JOB} sets no CIBW_BUILD on a pull request in a"
        " shape `_pull_request_selection` reads, and a job that does not"
        " narrow builds every interpreter"
    )


def test_a_pull_request_builds_a_free_threaded_interpreter_on_every_platform() -> None:
    """The classifier is a claim about what a pull request builds, per platform.

    The organization standard declares it where the gate refuses a landing
    that breaks the free-threaded build, and the required check on a pull
    request builds the interpreters `CIBW_BUILD` keeps, not the ones
    `[tool.cibuildwheel]` configures: the biconditional above asks the
    configuration, which a push to `main` and a release build whole, so a
    selection that dropped the free-threaded pattern would leave it green
    with the classifier still declared and nothing on a branch building
    the wheel it stands for.

    What it asks for is a free-threaded identifier, not `cp314t`: a
    selection naming the next free-threaded interpreter in its place
    passes, as the biconditional above accepts any interpreter ending in
    `t`. It is not a clause of that biconditional because it has a reader
    of its own, and a failure of that reader wants its own message. It asks
    once per cibuildwheel platform and not once per runner image: the
    architecture is the host's, as it is above.
    """
    lacking = _platforms_without_free_threaded(_gate_selection())
    assert not lacking, (
        f"the free-threading classifier is declared and the CIBW_BUILD a pull"
        f" request gives {_BUILD_JOB} builds no free-threaded identifier on"
        f" {', '.join(lacking)}"
    )


_CLASSIFIER_TEXT = (
    '    "Programming Language :: Python :: Free Threading :: 2 - Beta",\n'
)
_WITHOUT_FREE_THREADED = "cp310-* cp311-win_arm64"


def test_a_selection_without_the_free_threaded_pattern_lacks_it_everywhere(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The control for the test above: it can fail, and on every platform.

    A selection of `cp310-*` and `cp311-win_arm64` keeps no free-threaded
    identifier on any platform, and with `cp314t-*` added it keeps one on
    each. The classifier is appended to what `pyproject.toml` holds, so
    that this holds of a tree that stopped declaring it while
    `_require_cibuildwheel` still reads its floor. The caller's `CIBW_SKIP`,
    which alone would empty every answer, is exported first: the second
    assertion is then also the check that it does not reach cibuildwheel.
    The platforms are spelled out, so that one dropped from
    `_CIBW_PLATFORMS` is a difference here and not a shorter list to match.
    """
    monkeypatch.setattr(
        sys.modules[__name__], "_PYPROJECT", _PYPROJECT + _CLASSIFIER_TEXT
    )
    monkeypatch.setenv("CIBW_SKIP", "*")
    assert _platforms_without_free_threaded(_WITHOUT_FREE_THREADED) == [
        "linux",
        "macos",
        "windows",
    ]
    assert _platforms_without_free_threaded(f"{_WITHOUT_FREE_THREADED} cp314t-*") == []


def test_no_free_threaded_identifier_is_demanded_without_the_classifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tree that does not declare the classifier claims nothing about it.

    `_print_build_identifiers` is replaced by a call that fails the test
    if it is reached, so an answer of nothing lacking is not one that
    cibuildwheel gave.
    """

    def _unreached(platform: str, _environ: dict[str, str] | None = None) -> str:
        raise AssertionError(f"cibuildwheel asked about {platform} for no claim")

    monkeypatch.setattr(sys.modules[__name__], "_PYPROJECT", "[project]\n")
    monkeypatch.setattr(sys.modules[__name__], "_print_build_identifiers", _unreached)
    assert _platforms_without_free_threaded(_WITHOUT_FREE_THREADED) == []


_IF = "        if: github.event_name == 'pull_request'\n"
_SHELL = "        shell: bash\n"
_RUN = '        run: echo "CIBW_BUILD=cp310-* cp314t-*" >> "$GITHUB_ENV"\n'
_NARROWING = f"      - name: Narrow\n{_IF}{_SHELL}{_RUN}"
_ENV = "    env:\n"
_BUILD_STEP = "      - name: Build wheels\n        run: uv run cibuildwheel\n"
# a job of the shape the gate's is, cut to what the read looks at
_SAMPLE_JOB = (
    "    name: Build wheels on ${{ matrix.os }}\n"
    "    runs-on: ${{ matrix.os }}\n"
    f"{_ENV}"
    "      UV_PYTHON_DOWNLOADS: never\n"
    "    steps:\n"
    "      - name: Checkout code\n"
    "        uses: actions/checkout@v7\n"
    f"{_NARROWING}"
    f"{_BUILD_STEP}"
)


def test_the_step_is_read_by_what_it_writes_and_not_by_the_order_of_its_keys() -> None:
    """The accepted shape is three keys, whatever else the step carries.

    A reordering of the keys, the first of them on the dash line, is the
    same step; so is another value, which is returned as written.
    """
    assert _pull_request_selection(_SAMPLE_JOB) == "cp310-* cp314t-*"
    reordered = _SAMPLE_JOB.replace(
        _NARROWING,
        '      - run: echo "CIBW_BUILD=cp314t-*" >> "$GITHUB_ENV"\n'
        f"{_SHELL}{_IF}        name: Anything else\n",
    )
    assert reordered != _SAMPLE_JOB
    assert _pull_request_selection(reordered) == "cp314t-*"


@pytest.mark.parametrize(
    "old, new",
    [
        pytest.param(
            "      - name: Narrow\n",
            "      - name: Set CIBW_BUILD - the oldest, and the free-threaded one\n",
            id="a step named after the setting it sets, on its dash line",
        ),
        pytest.param(
            _NARROWING,
            f'      - run: echo "CIBW_BUILD=cp310-* cp314t-*" >> "$GITHUB_ENV"\n'
            f"{_IF}{_SHELL}        name: Set CIBW_BUILD\n",
            id="a step named after it, beside its keys",
        ),
        pytest.param(
            "      - name: Checkout code\n",
            "      - name: Clear CIBW_SKIP\n",
            id="another step naming a setting it does not set",
        ),
        pytest.param(
            "    name: Build wheels on ${{ matrix.os }}\n",
            "    name: Build wheels with CIBW_ENABLE on ${{ matrix.os }}\n",
            id="the job named after a setting it does not set",
        ),
    ],
)
def test_a_name_that_mentions_a_setting_sets_none(old: str, new: str) -> None:
    """A `name:` is prose, so the step is still found and no name is a second.

    The value is read from the step and not from anything a name says, and
    a `CIBW_` word inside a name does not make it a second setting, which
    would read as nothing. The three places a name sits are here, with a
    name mentioning the setting the step sets and another naming one that
    nothing sets.
    """
    assert old in _SAMPLE_JOB
    assert new != old
    named = _SAMPLE_JOB.replace(old, new)
    assert _pull_request_selection(named) == "cp310-* cp314t-*"


def test_a_name_that_mentions_a_setting_does_not_hide_a_real_second() -> None:
    """The names are dropped, and a `CIBW_` outside one still counts."""
    named = _SAMPLE_JOB.replace(
        "      - name: Checkout code\n", "      - name: Clear CIBW_SKIP\n"
    )
    assert _pull_request_selection(named) == "cp310-* cp314t-*"
    assert (
        _pull_request_selection(named.replace(_ENV, f"{_ENV}      CIBW_SKIP: '*'\n"))
        == ""
    )


@pytest.mark.parametrize(
    "old, new",
    [
        pytest.param(
            _IF,
            "        if: github.event_name == 'pull_request' && matrix.os != 'x'\n",
            id="a compound condition",
        ),
        pytest.param(
            _IF, "        if: github.event_name != 'push'\n", id="another condition"
        ),
        pytest.param(_IF, "", id="no condition"),
        pytest.param(
            "      - name: Narrow\n",
            "      - name: >-\n          Set CIBW_BUILD\n",
            id="a name folded over a second line naming a setting",
        ),
        pytest.param(_SHELL, "", id="the default shell"),
        pytest.param(_SHELL, "        shell: pwsh\n", id="another shell"),
        pytest.param(
            _SHELL,
            "        env:\n          shell: bash\n",
            id="a shell that is an env's and not the step's",
        ),
        pytest.param(
            _IF,
            "        with:\n          if: github.event_name == 'pull_request'\n",
            id="a condition that is an input's and not the step's",
        ),
        pytest.param(
            _RUN,
            '        with:\n          run: echo "CIBW_BUILD=cp314t-*" >> "$GITHUB_ENV"\n',
            id="a command that is an input's and not the step's",
        ),
        pytest.param(
            _NARROWING + _BUILD_STEP,
            _BUILD_STEP + _NARROWING,
            id="the step after the one that runs cibuildwheel",
        ),
        pytest.param(
            _BUILD_STEP,
            "      - name: Build wheels\n        run: echo built\n",
            id="no step that runs cibuildwheel",
        ),
        pytest.param(
            _RUN,
            '        run: |\n          echo "CIBW_BUILD=cp314t-*" >> "$GITHUB_ENV"\n',
            id="a block scalar",
        ),
        pytest.param(
            _RUN,
            '        run: echo "CIBW_BUILD=cp314t-*" >> "$GITHUB_OUTPUT"\n',
            id="another file",
        ),
        pytest.param(
            _RUN,
            '        run: echo "CIBW_BUILD=$PATTERNS" >> "$GITHUB_ENV"\n',
            id="an expansion",
        ),
        pytest.param(
            _RUN,
            '        run: echo "CIBW_BUILD=cp314t-* $PATTERNS" >> "$GITHUB_ENV"\n',
            id="an expansion after the first pattern",
        ),
        pytest.param(
            _RUN,
            '        run: echo "CIBW_BUILD=`id" >> "$GITHUB_ENV"\n',
            id="a backtick first",
        ),
        pytest.param(
            _RUN,
            '        run: echo "CIBW_BUILD=cp314t-* `id`" >> "$GITHUB_ENV"\n',
            id="a backtick after the first pattern",
        ),
        pytest.param(
            _RUN,
            '        run: echo "CIBW_BUILD=\\n" >> "$GITHUB_ENV"\n',
            id="a backslash first",
        ),
        pytest.param(
            _RUN,
            '        run: echo "CIBW_BUILD=cp314t-*\\n" >> "$GITHUB_ENV"\n',
            id="a backslash after the first pattern",
        ),
        pytest.param(
            _RUN,
            '        run: echo "CIBW_BUILD=a" ; echo "x" >> "$GITHUB_ENV"\n',
            id="a second command with a quote of its own",
        ),
        pytest.param(
            _RUN,
            '        run: echo "CIBW_BUILD="x" >> "$GITHUB_ENV"\n',
            id="a quote first in the value",
        ),
        pytest.param(
            _RUN,
            '        run: echo "CIBW_BUILD=cp314t-*" >> "$GITHUB_ENV" && echo done\n',
            id="text after the command",
        ),
        pytest.param(
            _RUN,
            '        run: FOO=1 echo "CIBW_BUILD=cp314t-*" >> "$GITHUB_ENV"\n',
            id="text before the command",
        ),
        pytest.param(
            _RUN,
            '        run: echo "CIBW_BUILD= " >> "$GITHUB_ENV"\n',
            id="a value of a space",
        ),
        pytest.param(
            _RUN,
            '        run: echo "CIBW_BUILD=" >> "$GITHUB_ENV"\n',
            id="no value",
        ),
        pytest.param(
            _RUN,
            "        env:\n          CIBW_BUILD: cp314t-*\n",
            id="a step's env and no command",
        ),
        pytest.param(
            _NARROWING,
            f'{_NARROWING}        env:\n          CIBW_SKIP: "*"\n',
            id="a second variable in the step",
        ),
        pytest.param(
            _NARROWING,
            f'{_NARROWING}      - run: echo "CIBW_BUILD=cp314t-*" >> "$GITHUB_ENV"\n',
            id="a second step setting it",
        ),
        pytest.param(_ENV, f"{_ENV}      CIBW_SKIP: '*'\n", id="a job's variable"),
    ],
)
def test_a_step_outside_the_accepted_shapes_reads_as_nothing(
    old: str, new: str
) -> None:
    """Each refusal is the accepted step with one thing changed.

    The change is asserted to change something, since a substitution
    aimed at text the job does not hold leaves the sample as it was and
    reads it, which is the control failing and not the refusal.
    """
    assert old in _SAMPLE_JOB
    assert new != old
    assert _pull_request_selection(_SAMPLE_JOB.replace(old, new)) == ""


def test_a_selection_set_outside_the_steps_reads_as_nothing() -> None:
    """A job-level `CIBW_BUILD` is no step's; a job of no steps reads none."""
    at_job_level = _SAMPLE_JOB.replace(_NARROWING, "").replace(
        _ENV, f"{_ENV}      CIBW_BUILD: cp314t-*\n"
    )
    assert "CIBW_BUILD: cp314t-*" in at_job_level
    assert _NARROWING not in at_job_level
    assert _pull_request_selection(at_job_level) == ""
    assert _pull_request_selection("") == ""


def test_the_gate_reads_its_build_job_without_its_comments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The workflow's own text is read through `_jobs`, comments dropped.

    A comment above the step naming two settings would be a second name
    in the job, and the read would be nothing; it is the value it is
    because the comment is gone. A workflow without the job is nothing.
    """
    gate = tmp_path / "test.yml"
    gate.write_text(
        "jobs:\n"
        f"  {_BUILD_JOB}:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      # CIBW_SKIP and CIBW_BUILD are what narrow the build\n"
        f"{_NARROWING}"
        f"{_BUILD_STEP}"
    )
    monkeypatch.setattr(sys.modules[__name__], "_GATE", gate)
    assert _gate_selection() == "cp310-* cp314t-*"
    gate.write_text("jobs:\n  changes:\n    runs-on: ubuntu-latest\n")
    assert _gate_selection() == ""


def test_cibuildwheel_is_asked_only_where_a_job_in_the_closure_calls_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`_cibuildwheel_free_threaded_interpreters` is not a fixed cost.

    A gate with no job that hands its build to cibuildwheel is the
    control this needs, since the real `test.yml` always has one: the
    monkeypatch below turns that function into a call that fails the test
    if it is ever reached, so a `_gate_interpreters` that asked it anyway
    -- ignoring the guard above it -- would be caught here rather than
    read as a passing gate that happened to find nothing.
    """
    gate = tmp_path / "test.yml"
    gate.write_text(
        "jobs:\n"
        "  changes:\n"
        "    name: Decide whether the matrix has anything to check\n"
        "    runs-on: ubuntu-latest\n"
        "  test-passed:\n"
        '    name: "test: every job passed"\n'
        "    needs: changes\n"
    )
    monkeypatch.setattr(sys.modules[__name__], "_GATE", gate)

    def _unreached() -> tuple[str, ...]:
        raise AssertionError("cibuildwheel asked where no job in the closure calls it")

    monkeypatch.setattr(
        sys.modules[__name__],
        "_cibuildwheel_free_threaded_interpreters",
        _unreached,
    )
    assert _gate_interpreters() == ()


def test_the_floor_is_the_test_groups_entry_and_not_the_build_groups() -> None:
    """`_CIBW_FLOOR` reads the one entry that carries a marker.

    `build` names cibuildwheel too, with no marker and a lower floor,
    and that lower floor is not the one an installed release is held to.
    """
    assert len(_CIBW_FLOOR.findall(_PYPROJECT)) == 1
    assert _CIBW_FLOOR.search('    "cibuildwheel>=2.23.4",\n') is None


def test_a_cibuildwheel_that_exits_non_zero_fails_with_its_own_stderr() -> None:
    """The refusal is the failure, and its reason is in the message.

    An unknown platform makes cibuildwheel exit non-zero, and argparse's
    own line for it names the value it refused.
    """
    with pytest.raises(pytest.fail.Exception) as refused:
        _print_build_identifiers("nonsense")
    message = str(refused.value)
    assert "exited 2" in message
    assert "invalid choice: 'nonsense'" in message


def test_the_callers_cibw_settings_do_not_reach_cibuildwheel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The answer is the tree's configuration, whatever the caller exported.

    `CIBW_SKIP=*` selects no identifier at all. The first assertion is the
    control, that the variable empties what cibuildwheel prints when it
    reaches it; the second, that the tree's own configuration prints
    something to be emptied; the last, that the default call prints that
    much with the variable set.
    """
    linux = "linux"
    inherited = _print_build_identifiers(linux, {**os.environ, "CIBW_SKIP": "*"})
    assert not inherited.strip()
    configured = _print_build_identifiers(linux)
    assert configured.strip()
    monkeypatch.setenv("CIBW_SKIP", "*")
    assert _print_build_identifiers(linux) == configured


def test_the_closure_reads_needs_in_each_of_its_three_shapes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job after the key, a flow list there, a block list under it.

    GitHub takes all three, `test.yml` writes all three, and they name
    the same jobs, so a reader of two of them answers a closure short
    of whatever sits behind an edge written in the third. Short in
    silence wherever the jobs the narrowing keeps still name an
    interpreter: what the free-threading check above reads is an empty
    interpreter tuple and not a short closure, `_closure` opening with
    the key itself, so a closure is never the empty thing. A narrowing
    reaching past every job that names one is caught there and a
    narrowing short of that is not (btclib-org/.github#1031). The job
    text below is its own rather than the gate's, the arrangements at
    issue being ones the gate does not write.

    A whole-line comment among the items, a blank line between two of
    them and a trailing comment on one each end a run of adjacent item
    lines, and a yaml parser reads each of them as the same two items
    (btclib-org/.github#1038). None of the forms below is invented:
    `_jobs` leaves a whole-line comment as a run of spaces one short of
    the indent it was written at, and a trailing comment written with
    two spaces before the `#` as a single space, where a copy of this
    module that keeps comments hands the same pattern the `#` itself --
    so both forms stand below, each spelled out rather than one reached
    from the other.

    The job dict is flat, so every case asserts the closure its own text
    earns: the aggregate and the one job a scalar names, where a list of
    either shape reaches both. A dict in which `changes` waited on
    `coverage` buys comparable expectations with a second route to
    `coverage`, and an item dropped below a residue is reached by that
    route anyway: the rows a whole-line comment and a blank line are
    written for then hold under a reader carrying no whole-line
    alternative at all (btclib-org/.github#1053). What the chain was also
    pinning, and what nothing else in this module pins, is that `_closure`
    walks: flat, one hop is the whole closure, and the gate's own
    aggregate names each job it waits on directly, so a reader taking a
    job's direct `needs:` and stopping answers every row here and the real
    gate alike. One chained dict stands below the flat rows for that
    alone, asserting its own closure and nothing about a shape.
    """

    def closure(needs: str) -> set[str]:
        jobs = {"aggregate": needs, "changes": "", "coverage": ""}
        return _closure(jobs, "aggregate")

    whole = {"aggregate", "changes", "coverage"}
    flow = "    needs: [changes, coverage]\n"
    scalar = "    needs: changes\n"
    under_the_key = {
        "a block list": "    needs:\n      - changes\n      - coverage\n",
        "a comment among the items": (
            "    needs:\n"
            "      - changes\n"
            "      # the cell the coverage floor is measured on\n"
            "      - coverage\n"
        ),
        "that comment stripped": (
            "    needs:\n      - changes\n     \n      - coverage\n"
        ),
        "a comment on an item": (
            "    needs:\n      - changes  # the gate\n      - coverage\n"
        ),
        "that one stripped": "    needs:\n      - changes \n      - coverage\n",
        "a blank line between two items": (
            "    needs:\n      - changes\n\n      - coverage\n"
        ),
    }
    # what the docstring says the stripped pair is: `_COMMENT` takes one
    # whitespace character with the `#` it removes, so the two forms
    # spelled out above stay the two a run through `_jobs` produces
    assert (
        _COMMENT.sub("", under_the_key["a comment among the items"])
        == under_the_key["that comment stripped"]
    )
    assert (
        _COMMENT.sub("", under_the_key["a comment on an item"])
        == under_the_key["that one stripped"]
    )
    assert closure(flow) == whole
    assert closure(scalar) == {"aggregate", "changes"}
    for shape, block in under_the_key.items():
        assert closure(block) == whole, shape
    # a job key may carry a hyphen, and an item token stopping at one
    # loses the job (btclib-org/.github#1063)
    hyphenated = {
        "aggregate": "    needs:\n      - test-passed\n      - free-threaded\n",
        "test-passed": "",
        "free-threaded": "",
    }
    assert _closure(hyphenated, "aggregate") == set(hyphenated)
    # the one job dict here that is not flat, and this module's only
    # assertion that a job reached only through another is reached at
    # all: with every dict flat one hop is the whole closure, so a
    # `_closure` that read a job's direct `needs:` and stopped would
    # answer every row above correctly
    chained = {
        "aggregate": scalar,
        "changes": "    needs: coverage\n",
        "coverage": "",
    }
    assert _closure(chained, "aggregate") == whole
    # the control: a reader of the key's own line and nothing under it
    # answers the same for the two shapes that write the list there and
    # the aggregate alone for those that write it under the key, so what
    # the assertions above turn on is the items being read rather than
    # the jobs merely being in the dict
    monkeypatch.setattr(
        sys.modules[__name__],
        "_NEEDS",
        re.compile(
            r"^    needs:(?P<inline>[^#\n]*)(?:#[^\n]*)?\n(?P<items>)", re.MULTILINE
        ),
    )
    assert closure(flow) == whole
    assert closure(scalar) == {"aggregate", "changes"}
    for shape, block in under_the_key.items():
        assert closure(block) == {"aggregate"}, shape


def test_the_closure_reads_no_step_of_a_job_as_a_job_it_waits_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `steps:` entry sits at the item indent and is not an item.

    `      - name: Setup uv` differs from an item in what follows the
    dash and in nothing else, so a run widened to take the rest of the
    line reads its first token as a job and goes on reading below it.
    What ends the run ahead of a real job's steps is the `steps:` key,
    written at the shallower indent a job's own attributes take, so the
    text the two readings disagree about is a step line where an item
    goes; the widened reader below is what says so, both readings
    answering alike on the job whose steps follow its `needs:`.

    `_closure` indexes `jobs` by each name it reads, so the widened
    reading costs a `KeyError` naming the step's own first token rather
    than a closure carrying it. The assertion is on that token: a
    `KeyError` alone would answer as readily to a job dict this test
    spelled wrong.
    """

    def closure(needs: str) -> set[str]:
        jobs = {"aggregate": needs, "changes": "", "coverage": ""}
        return _closure(jobs, "aggregate")

    steps = (
        "    needs:\n"
        "      - changes\n"
        "      - coverage\n"
        "    steps:\n"
        "      - name: Setup uv\n"
        "        uses: astral-sh/setup-uv@v7\n"
    )
    misplaced = (
        "    needs:\n      - changes\n      - name: Setup uv\n      - coverage\n"
    )
    assert closure(steps) == {"aggregate", "changes", "coverage"}
    assert closure(misplaced) == {"aggregate", "changes"}
    monkeypatch.setattr(
        sys.modules[__name__],
        "_NEEDS",
        re.compile(
            r"^    needs:(?P<inline>[^#\n]*)(?:#[^\n]*)?\n"
            r"(?P<items>(?:^      - \S+[^\n]*\n|^[ \t]*(?:#[^\n]*)?\n)*)",
            re.MULTILINE,
        ),
    )
    assert closure(steps) == {"aggregate", "changes", "coverage"}
    with pytest.raises(KeyError) as widened:
        closure(misplaced)
    assert widened.value.args == ("name:",)


def test_the_closure_takes_no_token_of_a_comment_on_the_needs_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `#` on the key's own line names no job the aggregate waits on.

    The inline half stops at the `#`, so a trailing comment there leaves
    the job before it and nothing else (btclib-org/.github#1038). A half
    reading the rest of the line -- the reader below -- hands the walk
    every word of the comment as a job key, and `_closure` indexes
    `jobs` by each of them, so the walk raises on the last word rather
    than returning a closure carrying all four. Both halves of that are
    asserted: `_waits_on` names the four tokens, and the `KeyError`
    names the one the walk reached first, which a bare `pytest.raises`
    would not tell from a dict this test spelled wrong.
    """

    def closure(needs: str) -> set[str]:
        # unstripped, which is what a copy of this module that keeps
        # comments hands the pattern
        return _closure({"aggregate": needs, "changes": ""}, "aggregate")

    annotated = "    needs: changes  # the gate\n"
    assert _waits_on(annotated) == ["changes"]
    assert closure(annotated) == {"aggregate", "changes"}
    monkeypatch.setattr(
        sys.modules[__name__],
        "_NEEDS",
        re.compile(
            r"^    needs:(?P<inline>[^\n]*)\n"
            r"(?P<items>(?:^      - \S+[ \t]*(?:#[^\n]*)?\n|^[ \t]*(?:#[^\n]*)?\n)*)",
            re.MULTILINE,
        ),
    )
    assert _waits_on(annotated) == ["changes", "#", "the", "gate"]
    with pytest.raises(KeyError) as widened:
        closure(annotated)
    assert widened.value.args == ("gate",)


def test_a_caller_shaped_with_reads_the_same_interpreters_as_a_block() -> None:
    """The shape a caller of `reusable-os-suite.yml` will carry.

    No such caller exists yet: `os-ubuntu.yml`, `os-macos.yml` and
    `os-windows.yml` still declare `_PYTHONS`'s own block sequence
    (btclib-org/.github#1119). This constructs the shape
    `reusable-deps-oldest.yml`'s own five callers already establish for
    one interpreter -- `python-version: "3.10"` -- widened the only way
    a `workflow_call` input can carry a list, JSON-encoded inside a
    quoted string, and checks that `_matrix` reads it the same as the
    block sequence it stands beside.
    """
    block = (
        '        python-version:\n          - "3.10"\n          - "3.11"\n'
        '          - "3.12"\n'
    )
    caller = '    with:\n      python-versions: \'["3.10", "3.11", "3.12"]\'\n'
    listed = ("3.10", "3.11", "3.12")
    assert _matrix(block) == listed
    assert _matrix(caller) == listed


def test_a_bare_with_and_a_matrix_expression_read_no_interpreter() -> None:
    """Neither an unrelated `with:` nor an expression is an interpreter list.

    The negative control the positive above needs: a pattern widened
    until it matches anything passes that one regardless. `with:` naming
    something other than the interpreters, and `python-versions:` naming
    an expression rather than a JSON string, are the two ways a caller's
    block can hold neither without the key itself being absent.
    """
    unrelated = "    with:\n      submodules: true\n"
    expression = "    with:\n      python-versions: ${{ matrix.python }}\n"
    assert _matrix(unrelated) == ()
    assert _matrix(expression) == ()
