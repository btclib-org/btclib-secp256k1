# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""`wheel-reproducibility.yml` builds on the platforms the release does.

`tests/interpreters_test.py` is the same shape one axis over: three
sentinels each carry their own copy of an interpreter list, nothing
compares them, and the three drift in the direction that is hardest to
notice. Here the axis is a platform rather than an interpreter, and
each matrix in `wheel-reproducibility.yml` is a hand-typed copy of one
job's in `test.yml`, kept in sync by a comment in each file rather than
by anything that fails when the two disagree. This is that check.

`rebuild`'s list and `build-cibuildwheel`'s are not equal, and #514 is
why: that job carries a second image for every platform, so that one
commit is built on two environments and not only in two directories of
one. Equality would forbid exactly the thing it exists to do. What has
to hold there is the containment -- an image `build-cibuildwheel`
builds a release wheel on and the sentinel does not is a wheel nothing
measures -- together with the pairing, since a platform left with one
image is one whose across-images comparison has nothing to compare.

`repaired`'s list is held the same way rebuild's is, and #515 is the
reason it starts there: that job asks whether the wheel the release
uploads reproduces, so every release image has to be among its own --
an image the release builds a wheel on and this job does not is a wheel
nothing measures. #524 is why it is a containment and not an equality,
though, unlike rebuild's: the release images stay held as a containment,
but linux-x86-64 and linux-aarch64 also carry a second image apiece,
reused from rebuild's own pair, for the container question #524 asks
that the runner's own toolchain does not answer. Every other platform
keeps exactly its one release image, since a second one there would
measure a toolchain the pinned container -- Linux's own object -- says
nothing about.

`dynamic`'s list is held against `build-dynamic`'s the same way and for
the same reason, that job being where the `py3-none-*` wheels #540 is
about are built and repaired. `build-windows` builds the remaining one
on a single runner with no matrix at all, so the sentinel's
`cross-windows` job has no list to hold against anything.

GitHub Actions gives one workflow no way to read another's
`strategy.matrix` short of `workflow_call`, which neither file uses --
so the two lists are not read from one another at runtime, and never
can be without wiring the sentinel into the gate, which
`wheel-reproducibility.yml`'s own header explains is not wanted. What is
checkable is that the two texts agree, which is what this asks on every
run of the suite instead of on whoever next edits one of the two files
and forgets the other.

The aggregate at the end of `wheel-reproducibility.yml` carries one more
copy of those matrices, inside the same file: `NEEDS_ROWS`, the name of
every row one of its `needs` jobs lists under when it runs, a matrix
job's once per entry with `matrix.os` expanded. A row that list misses
is still refused when the listing lags on it, so a list that has drifted
turns a green run red whenever the listing lags, which is
btclib-org/.github#1395's own defect come back. The last tests below
hold the list against each job's own `name:` and matrix, and
`NEEDS_RESULTS` against `needs:`.

The iOS wheels have a job in each file and no matrix: `build-ios` in
`test.yml` and `repaired-ios` in the sentinel. What is held of them is
the events each runs on, the image the two share, and that `check-dist`
asks for their wheels and the release downloads them.

macOS is arm64 alone, as section 10 of the organization's standard says.
What is held of it is that no workflow names an x86_64 macOS image, that
the dynamic macOS wheel is aimed at arm64 in both files, and that
`check-dist` admits a macOS wheel for arm64 alone and, at a release and
a dispatch, asks for a static and a dynamic one.

Read with a regex rather than parsed, for the same reason
`interpreters_test.py` gives: a workflow is yaml and no group here
carries a parser for it.
"""

import fnmatch
import re
import subprocess
from collections import defaultdict
from itertools import takewhile
from pathlib import Path

import pytest

from .ios_test import STARTS_A_PROCESS

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
# eight spaces with each entry indented two further
_OS_LIST = re.compile(r"^        os:\n(?P<block>(?:^          - \S+\n)+)", re.MULTILINE)
# and the bracketed shape a few jobs in test.yml carry instead, which is
# what `build-dynamic` writes its own list in. Reading both is what lets
# a list be compared against the job it was copied from without either
# file being reindented to suit this test
_OS_INLINE = re.compile(r"^        os: \[(?P<block>[^\]]+)\]$", re.MULTILINE)
# the sentinel's own shape, which is `include:` rather than a bare list:
# each entry names the platform its two images share and then the image.
# A comment between the two lines would be read as no entry at all,
# which the pairing check below turns red rather than passing over
_INCLUDE_ENTRY = re.compile(
    r"^          - platform: (?P<platform>\S+)\n            os: (?P<os>\S+)$",
    re.MULTILINE,
)


def _job_body(text: str, name: str) -> str:
    """Return one top-level job's own text, the next job's key excluded."""
    start = re.search(rf"^  {re.escape(name)}:\n", text, re.MULTILINE)
    assert start, f"no {name}: job in this workflow"
    rest = text[start.end() :]
    end = _NEXT_JOB.search(rest)
    return rest[: end.start()] if end else rest


def _os_list(body: str) -> tuple[str, ...]:
    """Return the `os:` list a job body names, in order, in either shape."""
    if block := _OS_LIST.search(body):
        return tuple(line.strip().lstrip("- ") for line in block["block"].splitlines())
    inline = _OS_INLINE.search(body)
    assert inline, "no os: list in this job, or not in either expected shape"
    return tuple(entry.strip() for entry in inline["block"].split(","))


def _images_by_platform(body: str) -> dict[str, list[str]]:
    """Return the images a job body's `include:` rows name.

    The result is keyed by platform.
    """
    images: dict[str, list[str]] = defaultdict(list)
    for entry in _INCLUDE_ENTRY.finditer(body):
        images[entry["platform"]].append(entry["os"])
    return images


_GATE_PLATFORMS = _os_list(_job_body(_GATE, "build-cibuildwheel"))
_SENTINEL_IMAGES = _images_by_platform(_job_body(_SENTINEL, "rebuild"))
_REPAIRED_IMAGES = _images_by_platform(_job_body(_SENTINEL, "repaired"))
_GATE_DYNAMIC_PLATFORMS = _os_list(_job_body(_GATE, "build-dynamic"))
_DYNAMIC_PLATFORMS = _os_list(_job_body(_SENTINEL, "dynamic"))
# the two platforms #524's own container question is about, and the only
# ones `repaired` carries a second image on
_LINUX_PLATFORMS = ("linux-x86-64", "linux-aarch64")


def test_every_platform_list_was_read() -> None:
    """Each list is non-empty, so the comparisons below are not vacuous.

    A job renamed, a matrix reindented, or any list rewritten in
    another shape would each leave one of these empty and every
    assertion below trivially true.
    """
    assert _GATE_PLATFORMS, "test.yml's build-cibuildwheel names no platform"
    assert _SENTINEL_IMAGES, "wheel-reproducibility.yml's rebuild names none"
    assert _REPAIRED_IMAGES, "wheel-reproducibility.yml's repaired names none"
    assert _GATE_DYNAMIC_PLATFORMS, "test.yml's build-dynamic names no platform"
    assert _DYNAMIC_PLATFORMS, "wheel-reproducibility.yml's dynamic names none"


def test_wheel_reproducibility_runs_on_every_wheel_platform() -> None:
    """The sentinel builds on every image the release builds a wheel on."""
    measured = {image for images in _SENTINEL_IMAGES.values() for image in images}
    missing = [image for image in _GATE_PLATFORMS if image not in measured]
    assert not missing, (
        f"build-cibuildwheel builds a wheel on {', '.join(missing)} and"
        " wheel-reproducibility.yml does not: a wheel the release ships"
        " that this measurement never reaches"
    )


def test_the_repaired_job_builds_every_release_image() -> None:
    """`repaired` asks about the uploaded wheel, so it never skips one."""
    measured = {image for images in _REPAIRED_IMAGES.values() for image in images}
    missing = [image for image in _GATE_PLATFORMS if image not in measured]
    assert not missing, (
        f"wheel-reproducibility.yml's repaired job is missing {', '.join(missing)},"
        " which build-cibuildwheel builds a release wheel on"
    )


def test_the_repaired_job_carries_a_second_image_on_linux_alone() -> None:
    """#524's own claim is about Linux, and the second image is #514's pair."""
    doubled = {
        platform: images
        for platform, images in _REPAIRED_IMAGES.items()
        if len(set(images)) >= 2
    }
    assert set(doubled) == set(_LINUX_PLATFORMS), (
        "wheel-reproducibility.yml's repaired job carries a second image on"
        f" {', '.join(sorted(doubled))}, and #524's own claim is about"
        f" {', '.join(_LINUX_PLATFORMS)} alone"
    )
    for platform, images in doubled.items():
        assert set(images) == set(_SENTINEL_IMAGES[platform]), (
            f"repaired's own images for {platform} are {sorted(set(images))},"
            f" not rebuild's own pair {sorted(set(_SENTINEL_IMAGES[platform]))}"
            " that #514 already measures there"
        )


def test_the_repaired_job_carries_one_image_off_linux() -> None:
    """A second image off Linux would measure a toolchain the pin ignores."""
    singles = {
        platform: images
        for platform, images in _REPAIRED_IMAGES.items()
        if platform not in _LINUX_PLATFORMS
    }
    not_one = {
        platform: images for platform, images in singles.items() if len(images) != 1
    }
    assert not not_one, (
        "wheel-reproducibility.yml's repaired job builds"
        f" {not_one} on more than the one release image off Linux"
    )


def test_the_dynamic_job_builds_the_release_images_and_no_others() -> None:
    """`dynamic` asks about the uploaded wheel too, so its images are those."""
    assert _DYNAMIC_PLATFORMS == _GATE_DYNAMIC_PLATFORMS, (
        "wheel-reproducibility.yml's dynamic job builds on"
        f" {', '.join(_DYNAMIC_PLATFORMS)} where build-dynamic uploads release"
        f" wheels from {', '.join(_GATE_DYNAMIC_PLATFORMS)}: the job that asks"
        " whether the uploaded wheel reproduces has to ask it of the images"
        " that upload one, and of no others"
    )


def test_every_platform_carries_a_second_image() -> None:
    """Each platform of `rebuild` is built on two images, as #514 asks.

    A platform down to one image measures whether that image builds one
    wheel twice, and says nothing about the environment being an input,
    while the run still goes green -- the `across-images` job names such
    a platform for the same reason.
    """
    # set(), not len(images): one image written twice is two entries and
    # one environment, and it would compare a wheel against itself
    alone = [
        platform
        for platform, images in _SENTINEL_IMAGES.items()
        if len(set(images)) < 2
    ]
    assert not alone, (
        f"{', '.join(alone)} is built on one image, so the across-images"
        " comparison has nothing to compare there"
    )


# the aggregate's `needs:` in the one-id-per-line shape it is written in
_NEEDS = re.compile(r"^    needs:\n(?P<block>(?:^      - \S+\n)+)", re.MULTILINE)
# a job's own `name:`, at the job's own indent, where a step's sits deeper
_JOB_NAME = re.compile(r"^    name: (?P<name>.+)$", re.MULTILINE)
_MATRIX_OS = "${{ matrix.os }}"
_AGGREGATE = _job_body(_SENTINEL, "reproducibility-passed")


def _env_block(key: str) -> list[str]:
    """Return the lines of one of the aggregate step's `|-` env values."""
    block = re.search(
        rf"^          {key}: \|-\n(?P<block>(?:^            \S.*\n)+)",
        _AGGREGATE,
        re.MULTILINE,
    )
    assert block, f"no {key} block scalar in the aggregate's step"
    return [line.strip() for line in block["block"].splitlines()]


def _needs() -> list[str]:
    """Return the ids the aggregate's own `needs:` names, in order."""
    block = _NEEDS.search(_AGGREGATE)
    assert block, "no needs: list in the aggregate, or not in the expected shape"
    return [line.strip().lstrip("- ") for line in block["block"].splitlines()]


def _rows(job_id: str) -> list[str]:
    """Return the names the job listing shows for one job's rows."""
    body = _job_body(_SENTINEL, job_id)
    name = _JOB_NAME.search(body)
    assert name, f"{job_id} declares no name:"
    if _MATRIX_OS not in name["name"]:
        return [name["name"]]
    images = [
        image for images in _images_by_platform(body).values() for image in images
    ] or list(_os_list(body))
    return [name["name"].replace(_MATRIX_OS, image) for image in images]


def test_the_aggregate_names_every_row_of_its_needs_jobs() -> None:
    """`NEEDS_ROWS` is each `needs` job's rows, matrix entries expanded."""
    needs = _needs()
    assert needs, "the aggregate's needs: names no job"
    expected = sorted(f"{job_id} {row}" for job_id in needs for row in _rows(job_id))
    assert sorted(_env_block("NEEDS_ROWS")) == expected, (
        "the aggregate's NEEDS_ROWS is not the rows its needs jobs list:"
        " a row it misses is refused whenever the listing lags on it"
    )


def test_the_aggregate_reads_every_needs_job_result() -> None:
    """`NEEDS_RESULTS` reads `needs.<id>.result` for each id, in order."""
    expected = [f"{job_id} ${{{{ needs.{job_id}.result }}}}" for job_id in _needs()]
    assert _env_block("NEEDS_RESULTS") == expected


# a job's own `if:`, as the folded scalar the iOS jobs write it in
_IF = re.compile(r"^    if: >-\n(?P<expr>(?:^      \S.*\n)+)", re.MULTILINE)
# the conditions the iOS jobs carry: the gate's skips a pull request and a
# push to a branch (a release is a push of a tag, and a dispatch is
# neither), the sentinel's a pull request, having no push trigger
_BUILD_IOS_IF = (
    "${{ !github.event.pull_request.draft"
    " && needs.changes.outputs.code == 'true'"
    " && github.event.action != 'closed'"
    " && github.event_name != 'pull_request'"
    " && !(github.event_name == 'push' && github.ref_type == 'branch') }}"
)
_REPAIRED_IOS_IF = (
    "${{ !github.event.pull_request.draft"
    " && needs.changes.outputs.build == 'true'"
    " && github.event_name != 'pull_request' }}"
)
# check-dist takes build-ios's skip, and every other need's success alone
_CHECK_DIST_IF = (
    "${{ !cancelled() && !github.event.pull_request.draft"
    " && github.event.action != 'closed'"
    " && needs.build-cibuildwheel.result == 'success'"
    " && needs.build-dynamic.result == 'success'"
    " && needs.build-sdist.result == 'success'"
    " && needs.build-windows.result == 'success'"
    " && (needs.build-ios.result == 'success'"
    " || needs.build-ios.result == 'skipped') }}"
)
_RUNS_ON = re.compile(r"^    runs-on: (?P<image>\S+)$", re.MULTILINE)
# what check-dist's step runs to refuse a dist without either iOS wheel
_IOS_PRESENCE = (
    "        shell: bash\n"
    "        run: |\n"
    "          shopt -s nullglob\n"
    "          device=(dist/*-cp3*-ios_*_arm64_iphoneos.whl)\n"
    "          simulator=(dist/*-cp3*-ios_*_arm64_iphonesimulator.whl)\n"
    "          if [ ${#device[@]} -eq 0 ] || [ ${#simulator[@]} -eq 0 ]; then\n"
    '            echo "::error::dist lacks an iOS device or an iOS simulator wheel"\n'
    "            exit 1\n"
    "          fi\n"
)
# a job's key, at the indent `jobs:` gives its entries, and one item of
# a `needs:` block list
_JOB_KEY = re.compile(r"^  (?P<key>[a-z0-9-]+):$", re.MULTILINE)
_ITEM = re.compile(r"^      - (?P<key>\S+)$", re.MULTILINE)
# what a job downloads artifacts by, as `download-artifact`'s input
_PATTERN = re.compile(r'^          pattern: "(\S+)"$', re.MULTILINE)


def _condition(body: str) -> str:
    """Return a job's own folded `if:`, on one line, or "" where it has none."""
    found = _IF.search(body)
    return " ".join(found["expr"].split()) if found else ""


def test_the_ios_jobs_skip_a_pull_request() -> None:
    """`build-ios` and `repaired-ios` skip a pull request.

    `build-ios` is test.yml's and also skips a push to a branch, and
    `repaired-ios` is wheel-reproducibility.yml's. Each `if:` is read
    whole: a clause dropped, or joined by `||`, is a different condition,
    and the test fails on it.
    """
    assert _condition(_job_body(_GATE, "build-ios")) == _BUILD_IOS_IF
    assert _condition(_job_body(_SENTINEL, "repaired-ios")) == _REPAIRED_IOS_IF


def test_the_condition_reader_sees_a_changed_clause() -> None:
    """The control the test above needs: one clause changed is a difference."""
    body = f"    if: >-\n      {_REPAIRED_IOS_IF}\n    runs-on: macos-latest\n"
    assert _condition(body) == _REPAIRED_IOS_IF
    widened = body.replace("!= 'pull_request'", "!= 'schedule'")
    assert widened != body
    assert _condition(widened) != _REPAIRED_IOS_IF
    assert _condition("    runs-on: macos-latest\n") == ""


def test_check_dist_asks_for_the_ios_wheels_at_a_release() -> None:
    """The step refuses a release or a dispatch that built no iOS wheel.

    check-dist takes `build-ios`'s skip, which a pull request always
    gives, so this step is what refuses that skip where it should not
    happen. Both wheels are asked for, the device's and the simulator's.
    """
    body = _job_body(_GATE, "check-dist")
    step = re.search(
        r"- name: Check the iOS wheels were built.*\n        if: (?P<cond>.*)\n"
        r"(?P<rest>(?:^ {8,}.*\n)+)",
        body,
        re.MULTILINE,
    )
    assert step, "check-dist has no step asking for the iOS wheels"
    assert step["cond"] == (
        "${{ inputs.use-signed-dist || github.event_name == 'workflow_dispatch' }}"
    )
    # whole, as the conditions above are: an `&&` for the `||` is a dist
    # with one of the two wheels that passes
    assert step["rest"] == _IOS_PRESENCE


def test_check_dist_waits_for_build_ios_and_takes_its_skip() -> None:
    """`build-ios` is a need of check-dist, and the only one it may skip.

    A skipped need skips a job whose `if:` opens with no status function,
    so the condition opens with one and names each need's result. The
    needs are read as a block list, the shape `tests/interpreters_test.py`
    reads too.
    """
    body = _job_body(_GATE, "check-dist")
    needs = _NEEDS.search(body)
    assert needs, "check-dist has no needs: block list"
    assert "build-ios" in _ITEM.findall(needs["block"])
    assert _condition(body) == _CHECK_DIST_IF


def test_test_passed_waits_for_every_job() -> None:
    """The gate's aggregate needs every other job of `test.yml`.

    A job missing from its `needs` is one whose failure the required
    check does not see: `build-ios` among them is a release whose iOS
    wheels failed and whose aggregate passed.
    """
    needs = _NEEDS.search(_job_body(_GATE, "test-passed"))
    assert needs, "test-passed has no needs: block list"
    # the keys under `jobs:` alone: the triggers under `on:` sit at the
    # same indent
    jobs = set(_JOB_KEY.findall(_GATE.split("\njobs:\n", 1)[1])) - {"test-passed"}
    assert "build-ios" in jobs
    assert set(_ITEM.findall(needs["block"])) == jobs


def test_the_ios_wheels_are_measured_on_the_image_that_builds_them() -> None:
    """`repaired-ios` builds for iOS on `build-ios`'s own image.

    The image carries the Xcode that compiles the wheel, which is the
    environment a reproduction is bound to.
    """
    gate = _job_body(_GATE, "build-ios")
    sentinel = _job_body(_SENTINEL, "repaired-ios")
    built = _RUNS_ON.search(gate)
    measured = _RUNS_ON.search(sentinel)
    assert built, "build-ios names no runs-on image"
    assert measured, "repaired-ios names no runs-on image"
    assert built["image"] == measured["image"]
    # GitHub's arm64 macOS image, which the simulator wheel's suite runs on
    assert built["image"] == "macos-latest"
    assert "cibuildwheel --platform ios\n" in gate
    assert "      CIBW_PLATFORM: ios\n" in sentinel


def test_the_release_publishes_the_ios_wheels() -> None:
    """The iOS artifact's name is one the publish jobs and check-dist download.

    Each of them takes the wheels by `pattern:`, so a name it does not
    match is a wheel built, tested and published nowhere.
    """
    release = (_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    upload = re.search(
        r"^          name: (?P<name>\S+)\n          path: \./wheelhouse/\*$",
        _job_body(_GATE, "build-ios"),
        re.MULTILINE,
    )
    assert upload, "build-ios uploads no artifact in the expected shape"
    for job, text in (
        ("publish-pypi", release),
        ("publish-testpypi", release),
        ("check-dist", _GATE),
    ):
        patterns = _PATTERN.findall(_job_body(text, job))
        assert patterns, f"{job} downloads no artifact by pattern"
        assert any(fnmatch.fnmatchcase(upload["name"], p) for p in patterns), job


# an x86_64 macOS runner label, as the standard's `tests/macos_test.py`
# spells it: GitHub's end in `-intel` or `-large`, and `-xlarge` is arm64
_X86_64_MACOS = re.compile(r"\bmacos-(?:\d+|latest)-(?:intel|large)\b")
# GitHub runs a workflow file of either suffix
_WORKFLOW_SUFFIXES = ("*.yml", "*.yaml")


def _workflows(directory: Path) -> list[Path]:
    """Return the workflow files of a directory, of either suffix, sorted."""
    return sorted(
        path for suffix in _WORKFLOW_SUFFIXES for path in directory.glob(suffix)
    )


_WORKFLOWS = _workflows(_ROOT / ".github/workflows")


@pytest.mark.parametrize(
    "line, expected",
    [
        ("runs-on: macos-26-intel", ["macos-26-intel"]),
        ("os: [ubuntu-latest, macos-15-intel]", ["macos-15-intel"]),
        ("          - macos-26-large", ["macos-26-large"]),
        ("# macos-latest-large is x86_64", ["macos-latest-large"]),
        ("os: [macos-latest, macos-15, macos-26-xlarge]", []),
    ],
)
def test_the_image_pattern_finds_an_x86_64_label_and_no_other(
    line: str, expected: list[str]
) -> None:
    """An `-intel` or `-large` label is found, and an arm64 one is not."""
    assert _X86_64_MACOS.findall(line) == expected


def test_the_workflow_listing_reads_both_suffixes(tmp_path: Path) -> None:
    """A `.yml` and a `.yaml` file are listed, and nothing else is."""
    for name in ("a.yml", "b.yaml", "c.txt", "d.yml.orig"):
        (tmp_path / name).touch()
    assert [path.name for path in _workflows(tmp_path)] == ["a.yml", "b.yaml"]


def test_no_workflow_names_an_x86_64_macos_image() -> None:
    """No line of a workflow names one, its comments included.

    Section 10 of the organization's standard refuses such a runner, and
    its `tests/macos_test.py` reads the strings of each parsed workflow.
    This module parses no yaml, so it reads every line instead.
    """
    assert _WORKFLOWS, "no workflow under .github/workflows"
    found = [
        f"{path.name}:{number}: {label}"
        for path in _WORKFLOWS
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        )
        for label in _X86_64_MACOS.findall(line)
    ]
    assert not found, f"x86_64 macOS images in the workflows: {found}"


# the step that aims a macOS dynamic build at arm64, in both files
_ARM64_ALONE = (
    "      - name: Aim the macOS build at arm64 and macOS 11.0\n"
    "        if: runner.os == 'macOS'\n"
    "        run: |\n"
    '          echo "MACOSX_DEPLOYMENT_TARGET=11.0" >> "$GITHUB_ENV"\n'
    '          echo "_PYTHON_HOST_PLATFORM=macosx-11.0-arm64" >> "$GITHUB_ENV"\n'
)


def test_the_dynamic_macos_wheel_is_built_for_arm64_alone() -> None:
    """`build-dynamic` and `dynamic` aim the macOS build at arm64 first.

    The interpreter setup-python installs is universal2: without the host
    platform the wheel is tagged universal2 and its library carries an
    x86_64 slice. The step is read whole, and before the build it feeds.
    """
    for text, job, build in (
        (_GATE, "build-dynamic", "- name: Build wheel\n"),
        (
            _SENTINEL,
            "dynamic",
            "- name: Build the dynamic wheel twice and diff the two archives\n",
        ),
    ):
        body = _job_body(text, job)
        assert body.count(_ARM64_ALONE) == 1, f"{job} does not aim at arm64"
        assert build in body, f"{job} has no step {build.strip()}"
        assert body.index(_ARM64_ALONE) < body.index(build), job


# check-dist's step that admits a macOS wheel for arm64 alone: its name,
# then its shell and its script, so an `if:` between them is no match
_ARM64_STEP = (
    "      - name: Check every macOS wheel is for arm64 alone\n"
    "        shell: bash\n"
    "        run: |\n"
)
# check-dist's step that asks for the arm64 macOS wheels, with the events
# it runs on: those of the iOS step
_PRESENCE_STEP = (
    "      - name: Check the arm64 macOS wheels were built (release and dispatch)\n"
    "        if: ${{ inputs.use-signed-dist"
    " || github.event_name == 'workflow_dispatch' }}\n"
    "        shell: bash\n"
    "        run: |\n"
)
_SCRIPT_INDENT = " " * 10
_BASH = Path("/bin/bash")


def _step(header: str) -> tuple[str, str]:
    """Return the check-dist step a header opens, and its script dedented."""
    body = _job_body(_GATE, "check-dist")
    assert body.count(header) == 1, f"check-dist lacks {header.splitlines()[0].strip()}"
    start = body.index(header)
    end = body.find("      - name: ", start + len(header))
    step = body[start:end] if end != -1 else body[start:]
    # the script is the lines at its indent, up to the first that is not
    lines = step[len(header) :].splitlines()
    script = takewhile(lambda line: line.startswith(_SCRIPT_INDENT), lines)
    return step, "".join(f"{line[len(_SCRIPT_INDENT) :]}\n" for line in script)


def test_check_dist_admits_a_macos_wheel_for_arm64_alone() -> None:
    """The step runs on every event, after the wheels are downloaded.

    It has no `if:` anywhere in it, and its script ends the job where it
    refuses a wheel. What it refuses is the test below's.
    """
    body = _job_body(_GATE, "check-dist")
    step, script = _step(_ARM64_STEP)
    assert "\n        if:" not in step
    assert body.index("- name: Download the wheels\n") < body.index(_ARM64_STEP)
    assert "for wheel in dist/*.whl; do\n" in script
    assert "  exit 1\n" in script


def test_check_dist_asks_for_the_arm64_macos_wheels_at_a_release() -> None:
    """The step runs at a release and a dispatch, after the download.

    The step above passes a dist with no macOS wheel, so this one is what
    refuses a release whose macOS build uploaded none. What it refuses is
    the test below's.
    """
    body = _job_body(_GATE, "check-dist")
    _, script = _step(_PRESENCE_STEP)
    assert body.index("- name: Download the wheels\n") < body.index(_PRESENCE_STEP)
    assert "  exit 1\n" in script


def _run_step(
    root: Path, names: list[str], header: str = _ARM64_STEP
) -> subprocess.CompletedProcess[str]:
    """Run a step's script as the runner does, on a `dist` of empty files."""
    dist = root / "dist"
    dist.mkdir(exist_ok=True)
    for name in names:
        (dist / name).touch()
    return subprocess.run(  # noqa: S603
        [
            str(_BASH),
            "--noprofile",
            "--norc",
            "-e",
            "-o",
            "pipefail",
            "-c",
            _step(header)[1],
        ],
        cwd=root,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )


@STARTS_A_PROCESS
@pytest.mark.skipif(not _BASH.exists(), reason="no /bin/bash to run the step")
@pytest.mark.parametrize(
    "tag, refused",
    [
        ("macosx_10_15_x86_64", True),
        ("macosx_10_9_intel", True),
        ("macosx_10_9_fat3", True),
        ("macosx_10_9_fat64", True),
        ("macosx_10_9_universal", True),
        ("macosx_11_0_universal2", True),
        ("macosx_10_13_x86_64.macosx_11_0_arm64", True),
        ("macosx_11_0_arm64.macosx_10_13_x86_64", True),
        ("MACOSX_11_0_X86_64", True),
        ("macosx_11_0_arm64.MACOSX_11_0_X86_64", True),
        ("macosx_11_0_arm64", False),
        ("macosx_11_0_ARM64", False),
        ("macosx_11_0_arm64.macosx_12_0_arm64", False),
        ("manylinux_2_28_x86_64", False),
        ("ios_13_0_arm64_iphonesimulator", False),
        ("win_amd64", False),
    ],
)
def test_the_step_refuses_every_macos_tag_but_arm64(
    tmp_path: Path, tag: str, refused: bool
) -> None:
    """A wheel with a macosx tag other than arm64 fails the step.

    The x86_64 tags are those packaging's `mac_platforms` gives pip on an
    x86_64 Mac, and a compressed set fails on whichever of its tags is
    not arm64. A tag is read without case, as packaging lowercases it.
    Wheels of the other platforms pass.
    """
    run = _run_step(tmp_path, [f"btclib_secp256k1-0.8.0.16-py3-none-{tag}.whl"])
    assert run.returncode == (1 if refused else 0), run.stdout + run.stderr


@STARTS_A_PROCESS
@pytest.mark.skipif(not _BASH.exists(), reason="no /bin/bash to run the step")
def test_the_step_reads_a_hostile_name_as_a_value(tmp_path: Path) -> None:
    """A name holding shell text runs none of it, admitted or refused."""
    admitted = "x-0-py3-none-$(touch a)`touch b`.macosx_11_0_arm64.whl"
    refused = "y-0-py3-none-macosx_10_9_x86_64;touch c.whl"
    run = _run_step(tmp_path, [admitted])
    assert run.returncode == 0, run.stdout + run.stderr
    run = _run_step(tmp_path, [refused])
    assert run.returncode == 1
    assert refused in run.stdout
    assert not [n for n in ("a", "b", "c") if (tmp_path / n).exists()]


# the wheels a release holds beside the macOS ones, and the two the step
# asks for
_OTHERS = [
    "btclib_secp256k1-0.8.0.16-cp315-cp315-manylinux_2_28_x86_64.whl",
    "btclib_secp256k1-0.8.0.16-cp315-cp315-win_amd64.whl",
    "btclib_secp256k1-0.8.0.16-cp315-cp315-ios_13_0_arm64_iphoneos.whl",
    "btclib_secp256k1-0.8.0.16-py3-none-manylinux_2_28_x86_64.whl",
    "btclib_secp256k1-0.8.0.16.tar.gz",
]
_STATIC = "btclib_secp256k1-0.8.0.16-cp315-cp315-macosx_11_0_arm64.whl"
_DYNAMIC = "btclib_secp256k1-0.8.0.16-py3-none-macosx_11_0_arm64.whl"


@STARTS_A_PROCESS
@pytest.mark.skipif(not _BASH.exists(), reason="no /bin/bash to run the step")
@pytest.mark.parametrize(
    "macos, refused",
    [
        ([_STATIC, _DYNAMIC], False),
        ([_DYNAMIC], True),
        ([_STATIC], True),
        ([], True),
    ],
    ids=["both", "no-static", "no-dynamic", "none"],
)
def test_the_step_refuses_a_dist_without_either_macos_wheel(
    tmp_path: Path, macos: list[str], refused: bool
) -> None:
    """A dist lacking the static or the dynamic arm64 wheel fails the step."""
    run = _run_step(tmp_path, _OTHERS + macos, _PRESENCE_STEP)
    assert run.returncode == (1 if refused else 0), run.stdout + run.stderr
