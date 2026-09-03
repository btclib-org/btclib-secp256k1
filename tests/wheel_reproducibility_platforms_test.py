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
    block = _OS_LIST.search(body)
    if block:
        return tuple(line.strip().lstrip("- ") for line in block["block"].splitlines())
    inline = _OS_INLINE.search(body)
    assert inline, "no os: list in this job, or not in either expected shape"
    return tuple(entry.strip() for entry in inline["block"].split(","))


def _images_by_platform(body: str) -> dict[str, list[str]]:
    """Return the images a job body's `include:` names, keyed by platform."""
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
