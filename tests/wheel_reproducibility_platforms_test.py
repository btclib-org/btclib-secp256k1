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

Read with a regex rather than parsed, for the same reason
`interpreters_test.py` gives: a workflow is yaml and no group here
carries a parser for it.
"""

import fnmatch
import re
from collections import defaultdict
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
# a platform written as the matrix's own axes, which is how the
# x86_64 macOS images are written: `exclude` removes only what the axes
# make, and a pull request builds none of them
_AXES = re.compile(
    r"^        platform: \[(?P<platform>[^\]]+)\]\n"
    r"        os: \[(?P<os>[^\]]+)\]$",
    re.MULTILINE,
)
# the `exclude:` expression a matrix carries, as a folded scalar
_EXCLUDE = re.compile(
    r"^        exclude: >-\n(?P<expr>(?:^          \S.*\n)+)", re.MULTILINE
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
    """Return the images a job body's `include:` rows and axes name.

    The result is keyed by platform.
    """
    images: dict[str, list[str]] = defaultdict(list)
    for entry in _INCLUDE_ENTRY.finditer(body):
        images[entry["platform"]].append(entry["os"])
    for axes in _AXES.finditer(body):
        images[axes["platform"]].extend(o.strip() for o in axes["os"].split(","))
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


def _exclusion(body: str) -> str:
    """Return the `exclude:` expression of a job body, on one line."""
    exclude = _EXCLUDE.search(body)
    assert exclude, "no exclude: expression in this job"
    return " ".join(exclude["expr"].split())


# where each file's matrices drop the Intel image: test.yml on a pull request
# and on a push to a branch (a release is a push of a tag, and a dispatch
# is neither), the sentinel on a pull request, having no push trigger
_GATE_SKIPS = (
    "(github.event_name == 'pull_request' || github.event_name == 'push'"
    " && github.ref_type == 'branch')"
)
_SENTINEL_SKIPS = "github.event_name == 'pull_request'"


def test_no_x86_64_macos_image_runs_where_the_calendar_alone_asks() -> None:
    """Each job listed below excludes its `-intel` image unless asked.

    CONTRIBUTING.md's *What gates a merge, and what only reports* gives
    the rule as this tree applies it. A job that lists such an image without
    excluding it would put it back on every pull request without a test
    failing, and the branches swapped would run it there alone.
    """
    jobs = [
        (_GATE, "build-cibuildwheel", "os", _GATE_SKIPS),
        (_GATE, "build-dynamic", "os", _GATE_SKIPS),
        (_SENTINEL, "rebuild", "platform", _SENTINEL_SKIPS),
        (_SENTINEL, "repaired", "platform", _SENTINEL_SKIPS),
        (_SENTINEL, "dynamic", "os", _SENTINEL_SKIPS),
    ]
    for text, name, key, skips in jobs:
        body = _job_body(text, name)
        listed = set(re.findall(r"macos-\d+-intel", body))
        assert listed, f"{name} names no x86_64 macOS image"
        # as include rows the image would escape the exclusion, which
        # removes only what the axes make
        rows = [e["os"] for e in _INCLUDE_ENTRY.finditer(body)]
        assert not [r for r in rows if r.endswith("-intel")], (
            f"{name} lists an -intel image as an include row"
        )
        value = "macos-x86-64" if key == "platform" else "macos-26-intel"
        expr = _exclusion(body)
        assert expr == (
            f"${{{{ fromJSON({skips} && '[{{\"{key}\": \"{value}\"}}]' || '[]') }}}}"
        ), f"{name} does not exclude {value} where it should: {expr}"


def test_check_dist_asks_for_the_x86_64_macos_wheels_at_a_release() -> None:
    """The step refuses a release or a dispatch that built no Intel wheel."""
    body = _job_body(_GATE, "check-dist")
    step = re.search(
        r"- name: Check the x86_64 macOS wheels were built.*\n        if: (?P<cond>.*)\n",
        body,
    )
    assert step, "check-dist has no step asking for the x86_64 macOS wheels"
    assert step["cond"] == (
        "${{ inputs.use-signed-dist || github.event_name == 'workflow_dispatch' }}"
    )


# a job's own `if:`, as the folded scalar the iOS jobs write it in
_IF = re.compile(r"^    if: >-\n(?P<expr>(?:^      \S.*\n)+)", re.MULTILINE)
# the conditions the iOS jobs carry: the gate's skips a pull request and a
# push to a branch, as `_GATE_SKIPS` excludes the Intel image there, and
# the sentinel's a pull request, as `_SENTINEL_SKIPS` does
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


def test_the_ios_jobs_skip_where_the_x86_64_macos_cells_do() -> None:
    """`build-ios` and `repaired-ios` run on the events the Intel image does.

    They have no matrix to exclude from, so the events are their `if:`,
    and each is read whole: a clause dropped, or joined by `||`, is a
    condition that builds iOS on a pull request, or on no release.
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
