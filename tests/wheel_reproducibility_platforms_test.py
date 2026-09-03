# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""`wheel-reproducibility.yml` builds on the platforms the release does.

`tests/interpreters_test.py` is the same shape one axis over: three
sentinels each carry their own copy of an interpreter list, nothing
compares them, and the three drift in the direction that is hardest to
notice. Here it is one pair rather than three, and one platform axis
rather than an interpreter one -- `wheel-reproducibility.yml`'s own
matrix is a hand-typed copy of `build-cibuildwheel`'s in `test.yml`,
kept in sync by a comment in each file rather than by anything that
fails when the two disagree. This is that check.

`rebuild`'s list and `build-cibuildwheel`'s are not equal, and #514 is
why: that job carries a second image for every platform, so that one
commit is built on two environments and not only in two directories of
one. Equality would forbid exactly the thing it exists to do. What has
to hold there is the containment -- an image `build-cibuildwheel`
builds a release wheel on and the sentinel does not is a wheel nothing
measures -- together with the pairing, since a platform left with one
image is one whose across-images comparison has nothing to compare.

`repaired`'s list is held as equality instead, and #515 is why: that
job asks whether the wheel the release uploads reproduces, so its
images are the release's and a second one would be a platform measured
twice. An image in one list and not the other is a defect in whichever
direction it falls -- one it builds and the release does not is
runner-minutes spent on a wheel nobody installs.

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
# eight spaces with each entry indented two further -- the shape
# test.yml uses for this particular list, distinct from the bracketed
# `os: [a, b]` a few other jobs in it carry for theirs
_OS_LIST = re.compile(r"^        os:\n(?P<block>(?:^          - \S+\n)+)", re.MULTILINE)
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
    """Return the `os:` list a job body names, in order."""
    match = _OS_LIST.search(body)
    assert match, "no os: list in this job, or not in the expected shape"
    return tuple(line.strip().lstrip("- ") for line in match["block"].splitlines())


def _images_by_platform(body: str) -> dict[str, list[str]]:
    """Return the images a job body's `include:` names, keyed by platform."""
    images: dict[str, list[str]] = defaultdict(list)
    for entry in _INCLUDE_ENTRY.finditer(body):
        images[entry["platform"]].append(entry["os"])
    return images


_GATE_PLATFORMS = _os_list(_job_body(_GATE, "build-cibuildwheel"))
_SENTINEL_IMAGES = _images_by_platform(_job_body(_SENTINEL, "rebuild"))
_REPAIRED_PLATFORMS = _os_list(_job_body(_SENTINEL, "repaired"))


def test_the_three_platform_lists_were_read() -> None:
    """Each list is non-empty, so the comparisons below are not vacuous.

    A job renamed, a matrix reindented, or any list rewritten in
    another shape would each leave one of these empty and every
    assertion below trivially true.
    """
    assert _GATE_PLATFORMS, "test.yml's build-cibuildwheel names no platform"
    assert _SENTINEL_IMAGES, "wheel-reproducibility.yml's rebuild names none"
    assert _REPAIRED_PLATFORMS, "wheel-reproducibility.yml's repaired names none"


def test_wheel_reproducibility_runs_on_every_wheel_platform() -> None:
    """The sentinel builds on every image the release builds a wheel on."""
    measured = {image for images in _SENTINEL_IMAGES.values() for image in images}
    missing = [image for image in _GATE_PLATFORMS if image not in measured]
    assert not missing, (
        f"build-cibuildwheel builds a wheel on {', '.join(missing)} and"
        " wheel-reproducibility.yml does not: a wheel the release ships"
        " that this measurement never reaches"
    )


def test_the_repaired_job_builds_the_release_images_and_no_others() -> None:
    """`repaired` asks about the uploaded wheel, so its images are those."""
    assert _REPAIRED_PLATFORMS == _GATE_PLATFORMS, (
        "wheel-reproducibility.yml's repaired job builds on"
        f" {', '.join(_REPAIRED_PLATFORMS)} where build-cibuildwheel builds"
        f" release wheels on {', '.join(_GATE_PLATFORMS)}: the job that asks"
        " whether the uploaded wheel reproduces has to ask it of the images"
        " that upload one, and of no others"
    )


def test_every_platform_carries_a_second_image() -> None:
    """Each platform is built on two images, which is what #514 asks.

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
