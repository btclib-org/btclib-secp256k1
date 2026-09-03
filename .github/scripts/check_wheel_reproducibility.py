# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

r"""Compare the wheels one commit builds, in one environment or across two.

`btclib-org/btclib-secp256k1#439` asks whether a wheel this project
builds reproduces byte for byte. `#497` and `#498` answered that for
macOS, by hand, building twice and comparing; `#500` is the same
measurement made repeatable and reaching the platforms a laptop cannot.
This script is that measurement, `wheel-reproducibility.yml` is what
runs it on every platform the release builds a wheel on, and which
platforms answer green is that workflow's own output rather than a list
kept here.

The first version of this script built twice from the one checkout it
ran in, which answers "does this checkout build the same wheel twice"
rather than #439's own question, "does this commit build the same
wheel". The two agree only where nothing in the build depends on
*where* it ran -- `#503` was exactly the case where they did not: the
static extension's debug map embedded the build directory's absolute
path, constant across two builds sharing one directory and invisible to
them for that reason. `copy_source_tree` below is what closes that gap:
each build gets its own fresh copy of `HEAD`, extracted into a directory
this script names, so the two builds' paths differ the way two
developers' checkouts, or a checkout and a release rebuild, actually do.
The two names differ in length as well as in content -- `a` and a much
longer second name -- since a difference held in a fixed-width field
could survive two same-length paths and still show up against a real
one. Building from `HEAD` rather than from the checkout in place is a
deliberate change from the first version: an uncommitted edit sitting in
the checkout is not part of what either build sees, since it is not
part of the commit the question is about.

Two directories are still one environment, and `#514` is the other
half: section 12 of the organization standard says the wheels do not
reproduce because the compiler, its version and the toolchain the
runner happened to have are unpinned inputs, and `RELEASING.md` says
the same of a rebuild on a second image -- which is a claim about two
environments and not about two directories.
`--across-images` is the entry point that asks it. The comparison
cannot happen where either build does, the two builds being on two
machines, so each `--keep-wheel` run saves its first build's wheel and
a later run compares the saved wheels: `wheel-reproducibility.yml`
carries them between the two as artifacts.

A whole-archive digest says two wheels differ and nothing past that.
`#497`'s own reading of a difference this coarse -- which byte, in which
member, and why -- took a person an evening once the digests alone had
already said "no". `diff_wheels` compares the two archives member by
member instead: which members are present, in which order, and for every
member both sides share, whether its bytes agree and whether its stored
`mtime`, permission bits and compression method do. A red run therefore
names a member and a field rather than a wheel.

The wheel's own filename is one of those lines and not a reason to stop
comparing. Two images of one platform can tag the wheel differently
without a byte of the build having moved -- a macOS runner's deployment
target reaches the platform tag, so `macosx_15_0` against `macosx_26_0`
is a name difference that says nothing yet about the members underneath
it. Reporting it as its own line and then comparing the members anyway
is what keeps a name difference from reading as a byte difference, and a
byte difference from hiding behind a name that agreed.

`uv build` is not what the release uploads, and `#515` is that gap.
`cibuildwheel` runs the same `scripts/cffi_build.py` and then repairs
the wheel with the tool it defaults to on the platform -- `auditwheel`
on Linux, `delocate` on macOS, `delvewheel` on Windows, since
`[tool.cibuildwheel]` names no `repair-wheel-command` of its own. What
that hands back is the repair's own file rather than the build's.
`--repaired` is the entry point that builds through `cibuildwheel`
instead, so that the archive PyPI receives is the one compared. It is
the same two directories and the same member-by-member
diff; what differs is that one build can leave more than one wheel,
Linux producing a `manylinux` and a `musllinux` wheel from the one
interpreter, so the two sides are paired by filename rather than taken
as one wheel each.

Run it from a checkout with the submodule initialized, and with the
commit under test the current `HEAD`:

    uv run --no-project python \\
        .github/scripts/check_wheel_reproducibility.py

`--keep-wheel <dir>` adds a copy of the first build's wheel under
`<dir>`, and `--across-images <dir>` compares wheels already built:
`<dir>` holds one directory per platform, each holding one directory
per image, each of those holding that image's wheel. `--repaired` takes
no argument and needs `cibuildwheel` on `PATH`, which is the `build`
dependency group, and `SOURCE_DATE_EPOCH` set in the environment first,
or this entry point refuses to run:

    export SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct)
    uv run --locked --only-group build python \\
        .github/scripts/check_wheel_reproducibility.py --repaired

Which interpreters that builds is `cibuildwheel`'s own to decide, and
`CIBW_BUILD` in the caller's environment is what narrows it;
`wheel-reproducibility.yml` sets that and the reasoning is there, this
script imposing no policy on a matrix it does not own.
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from collections.abc import Iterator
from pathlib import Path

_UV = shutil.which("uv") or "uv"
# resolved once: a bare "git" in a subprocess list is what S607 is about,
# the same way .github/scripts/check_submodule_pin.py resolves it
_GIT = shutil.which("git") or "git"
# the same resolution, and the fallback matters more here: cibuildwheel
# is in the build dependency group and not in the test one, so the suite
# importing this module finds nothing to resolve and the literal is what
# a test then sees on a faked command line
_CIBUILDWHEEL = shutil.which("cibuildwheel") or "cibuildwheel"
_ROOT = Path(__file__).resolve().parents[2]

# what #497 checked by hand -- order, permissions, compression and every
# timestamp -- read back from zipfile.ZipInfo rather than from otool or a
# hex dump: date_time is the member's stored mtime, external_attr carries
# the unix permission bits in its upper sixteen, and compress_type is
# STORED or DEFLATED. header_offset and internal_attr are not here: the
# first moves with every earlier member's compressed size and would flood
# a real content difference with offset noise for every member after it,
# and the second is not one hatchling or cffi's build ever sets
_METADATA_FIELDS = ("date_time", "external_attr", "compress_type")


def _extract_archive(source: Path, dest: Path) -> None:
    """Extract `source`'s `HEAD` commit into the fresh directory `dest`.

    `git archive` walks the tree the commit itself names, so what lands
    in `dest` is exactly what that commit tracks -- nothing an earlier
    build left in `source`, and nothing `.gitignore` excludes there
    either, which a plain recursive file copy would have to filter for
    itself instead of getting for free.

    Args:
        source: a git checkout, read at its current `HEAD`.
        dest: a directory to extract into. It may already exist -- an
            outer `git archive` leaves an empty directory at a gitlink's
            own path, which is where `copy_source_tree` below points the
            submodule's own extraction -- but is created if it does not.

    Raises:
        subprocess.CalledProcessError: `git archive` itself failed.
    """
    archived = subprocess.run(  # noqa: S603
        [_GIT, "archive", "--format=tar", "HEAD"],
        cwd=source,
        check=True,
        stdout=subprocess.PIPE,
    )
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archived.stdout)) as archive:
        # PEP 706's data filter is set on the TarFile rather than passed
        # as extractall(filter="data"): that keyword is a TypeError on
        # Python 3.10.11, which is what cibuildwheel pins cp310 to on the
        # macOS and Windows images -- one patch release below the 3.10.12
        # that backported the feature, and older than the 3.10 a manylinux
        # image carries, so the same call is fine on Linux and fatal on
        # the other two. An assignment is one statement on every
        # interpreter, where hasattr or sys.version_info is a branch no
        # single interpreter takes both ways and .github/scripts is
        # measured under the fail_under = 100 coverage floor. Setting
        # nothing at all is the other shape and costs a different red:
        # 3.12 and 3.13 raise a DeprecationWarning where no filter is set,
        # and pyproject.toml's filterwarnings = ["error"] makes that a
        # failing test. getattr with a default is what the tarfile
        # documentation gives for spanning versions with and without the
        # feature, and is an expression rather than a branch for the same
        # reason as above. Where data_filter is absent the fallback is
        # fully_trusted: a member named ../x is extracted outside dest,
        # which is CPython's own behaviour before the filter existed. What
        # makes that acceptable is the archive -- `git archive HEAD` over
        # this repository, from a checkout the caller is about to build --
        # and tests/wheel_reproducibility_test.py asserts it, no
        # interpreter the local gate runs having a fallback to take. S202
        # reads the extractall call rather than the attribute set beside
        # it, which is what the suppression on that line answers
        archive.extraction_filter = getattr(
            tarfile, "data_filter", (lambda member, _path: member)
        )
        archive.extractall(dest)  # noqa: S202


def copy_source_tree(root: Path, dest: Path) -> None:
    """Copy `root`'s checked-out commit, submodule included, into `dest`.

    `root` itself is never read past its git history: everything `uv
    build` needs comes out of two `git archive` calls, one for `root`
    and one for the `secp256k1` submodule inside it, since a gitlink is a
    commit reference rather than a tree and the outer archive does not
    walk into it.

    Args:
        root: the checkout to copy, submodule included.
        dest: where to copy `root`'s commit into. Meant to be fresh --
            the caller names it, and this function never reuses one it
            created itself -- but nothing here refuses an existing,
            populated `dest`; it would just extract on top of whatever
            is already there.

    Raises:
        subprocess.CalledProcessError: either `git archive` call failed.
    """
    _extract_archive(root, dest)
    _extract_archive(root / "secp256k1", dest / "secp256k1")


def build_wheel(source_dir: Path, out_dir: Path) -> Path:
    """Build `source_dir`'s wheel into `out_dir`, and return its path.

    Args:
        source_dir: the checkout, or copy of one, to build from. `uv
            build` runs with this as its working directory, which is
            what makes the path this build embeds, if it embeds one at
            all, the path a caller chose rather than one every build
            shares.
        out_dir: where `uv build` should write the wheel. Each call gets
            its own, rather than one directory reused twice, so that a
            failure on the second build leaves the first wheel on disk
            to compare by hand.

    Returns:
        The one wheel `out_dir` holds afterwards.

    Raises:
        subprocess.CalledProcessError: `uv build` itself failed.
        RuntimeError: the build left `out_dir` with a member count other
            than one -- zero having built nothing, more than one being a
            stale wheel from an interrupted earlier run sharing the
            directory, since `uv build` never removes what it did not
            just write.
    """
    subprocess.run(  # noqa: S603
        [_UV, "build", "--wheel", "--out-dir", str(out_dir)],
        cwd=source_dir,
        check=True,
    )
    wheels = sorted(out_dir.glob("*.whl"))
    if len(wheels) != 1:
        msg = f"expected exactly one wheel in {out_dir}, found {wheels}"
        raise RuntimeError(msg)
    return wheels[0]


def build_repaired_wheels(source_dir: Path, out_dir: Path) -> list[Path]:
    """Build `source_dir`'s repaired wheels into `out_dir`, and return them.

    `cibuildwheel` is invoked with `source_dir` as both the working
    directory and the package directory, which is the one shape it
    accepts: it refuses a package directory that is not inside the
    directory it was started in. Resolving the executable to an absolute
    path is what lets the working directory be the copy rather than the
    checkout the environment was built in.

    Args:
        source_dir: the copy of the checkout to build from.
        out_dir: where `cibuildwheel` should leave the repaired wheels.
            Each call gets its own, so that a failure on the second
            build leaves the first build's wheels to compare by hand.

    Returns:
        Every wheel `out_dir` holds afterwards, sorted by path. More
        than one is the ordinary Linux answer -- one interpreter there
        builds a `manylinux` wheel and a `musllinux` one, in two
        containers.

    Raises:
        subprocess.CalledProcessError: `cibuildwheel` itself failed.
        RuntimeError: it exited zero having written no wheel, which
            `--allow-empty` and a `skip` covering every identifier would
            both produce and neither is something to compare.
    """
    subprocess.run(  # noqa: S603
        [_CIBUILDWHEEL, "--output-dir", str(out_dir), "."],
        cwd=source_dir,
        check=True,
    )
    wheels = sorted(out_dir.glob("*.whl"))
    if not wheels:
        msg = f"cibuildwheel left no wheel in {out_dir}"
        raise RuntimeError(msg)
    return wheels


def diff_wheels(
    first: Path, second: Path, *, first_label: str, second_label: str
) -> list[str]:
    """Return one line per way the two wheels disagree, member by member.

    Args:
        first: one build's wheel.
        second: another build's wheel of the same commit.
        first_label: what to call `first` where a line has to say which
            side it is about -- which of two builds, or which image.
        second_label: the same, for `second`. Two wheels of one commit
            usually carry the same filename, which is why the label is
            the caller's to give rather than read off the path.

    Returns:
        An empty list where the two archives are indistinguishable, their
        filename included; otherwise one entry per difference, naming the
        member and, for a metadata disagreement, the field and both
        values.
    """
    complaints: list[str] = []
    if first.name != second.name:
        complaints.append(
            f"the wheel is named {first.name} on {first_label} and "
            f"{second.name} on {second_label}"
        )
    with zipfile.ZipFile(first) as za, zipfile.ZipFile(second) as zb:
        names_a = [info.filename for info in za.infolist()]
        names_b = [info.filename for info in zb.infolist()]
        by_name_a = {info.filename: info for info in za.infolist()}
        by_name_b = {info.filename: info for info in zb.infolist()}

        only_in_a = [name for name in names_a if name not in by_name_b]
        only_in_b = [name for name in names_b if name not in by_name_a]
        if only_in_a:
            complaints.append(f"only in {first_label}: {only_in_a}")
        if only_in_b:
            complaints.append(f"only in {second_label}: {only_in_b}")

        shared = [name for name in names_a if name in by_name_b]
        if not only_in_a and not only_in_b and names_a != names_b:
            complaints.append(
                f"member order differs: {names_a} on {first_label}, "
                f"{names_b} on {second_label}"
            )

        for name in shared:
            info_a, info_b = by_name_a[name], by_name_b[name]
            content_a, content_b = za.read(name), zb.read(name)
            if content_a != content_b:
                complaints.append(
                    f"{name}: content differs "
                    f"({len(content_a)} vs {len(content_b)} bytes, "
                    f"crc32 {info_a.CRC:08x} vs {info_b.CRC:08x})"
                )
            for field in _METADATA_FIELDS:
                value_a, value_b = getattr(info_a, field), getattr(info_b, field)
                if value_a != value_b:
                    complaints.append(f"{name}: {field} {value_a!r} vs {value_b!r}")
    return complaints


def pair_wheels_by_name(
    first: list[Path], second: list[Path], *, first_label: str, second_label: str
) -> list[str]:
    """Return one line per way two builds' sets of wheels disagree.

    Args:
        first: one build's wheels.
        second: another build's wheels, of the same commit.
        first_label: what to call `first` where a line has to say which
            side it is about.
        second_label: the same, for `second`.

    Returns:
        An empty list where the two builds produced the same wheels,
        name for name and member for member; otherwise one entry per
        difference, each prefixed with the wheel it is about. A wheel
        only one side built is a line of its own: the two are then not
        comparable, which is a different answer from their disagreeing
        and must not print like one.

        The prefix is what `diff_wheels` alone cannot supply and what
        one build leaving several wheels makes necessary: on Linux a
        single interpreter yields a `manylinux` wheel and a `musllinux`
        one, so every member of the package appears in this list twice
        and the two entries are otherwise the same words. That is the
        reason `compare_across_images` prefixes its own lines with the
        platform, and the same reason applies one level down.
    """
    by_name_first = {wheel.name: wheel for wheel in first}
    by_name_second = {wheel.name: wheel for wheel in second}
    complaints = [
        f"only {first_label} built {name}"
        for name in sorted(set(by_name_first) - set(by_name_second))
    ]
    complaints += [
        f"only {second_label} built {name}"
        for name in sorted(set(by_name_second) - set(by_name_first))
    ]
    for name in sorted(set(by_name_first) & set(by_name_second)):
        complaints += [
            f"{name}: {complaint}"
            for complaint in diff_wheels(
                by_name_first[name],
                by_name_second[name],
                first_label=first_label,
                second_label=second_label,
            )
        ]
    return complaints


def compare_one_platform(platform: Path) -> list[str]:
    """Return one line per way one platform's images disagree.

    Args:
        platform: a directory holding one subdirectory per image that
            built this platform's wheel, each with that wheel in it. The
            first image in sorted order is the one every other is
            compared against, so that a platform built on more than two
            images still yields one line per disagreeing pair.

    Returns:
        An empty list where every image's wheel matches the first one's.
        A directory that does not hold exactly one wheel is a line here
        too, and so is a platform left with fewer than two of them: the
        comparison this directory exists for did not happen, which is
        not the same answer as the wheels agreeing and must not print
        like it.
    """
    complaints: list[str] = []
    wheels: dict[str, Path] = {}
    for image in sorted(path for path in platform.iterdir() if path.is_dir()):
        found = sorted(image.glob("*.whl"))
        if len(found) == 1:
            wheels[image.name] = found[0]
        else:
            complaints.append(
                f"{image.name} left {[wheel.name for wheel in found]}, not one wheel"
            )
    if len(wheels) < 2:
        complaints.append(
            f"a wheel came back from {sorted(wheels)} alone, so no two images"
            " were compared"
        )
        return complaints
    reference, *others = sorted(wheels)
    for other in others:
        complaints += diff_wheels(
            wheels[reference],
            wheels[other],
            first_label=reference,
            second_label=other,
        )
    return complaints


def compare_across_images(root: Path) -> int:
    """Compare, platform by platform, the wheels its images built.

    Args:
        root: a directory holding one subdirectory per platform, in the
            shape `compare_one_platform` reads.

    Returns:
        The process exit code: zero where every platform's images agree.
        An empty `root` is not agreement either -- a run whose builds all
        failed downloads nothing and would otherwise print no line at
        all and exit green.
    """
    platforms = sorted(path for path in root.iterdir() if path.is_dir())
    if not platforms:
        print(f"::error::no platform built a wheel under {root}", file=sys.stderr)
        return 1

    failed = False
    for platform in platforms:
        complaints = compare_one_platform(platform)
        if complaints:
            failed = True
            for complaint in complaints:
                print(f"::error::{platform.name}: {complaint}", file=sys.stderr)
        else:
            print(f"{platform.name}: its images agree, member for member")
    return 1 if failed else 0


@contextlib.contextmanager
def two_source_copies() -> Iterator[tuple[Path, Path]]:
    """Yield two fresh copies of this commit, under a directory of their own.

    Both entry points that build want the same pair, and the pair is
    what carries `#503`'s property, so the two names are decided here
    rather than once per caller.

    Yields:
        The two source directories, in the order they are to be built.
        They differ in name length as well as in name -- see this
        module's own docstring for why a same-length pair would not
        do -- and they share a parent, which is where a caller puts its
        own output directories.
    """
    with tempfile.TemporaryDirectory(prefix="wheel-reproducibility-") as tmp:
        root = Path(tmp)
        first = root / "a"
        second = root / "a-second-directory-with-a-much-longer-name"
        copy_source_tree(_ROOT, first)
        copy_source_tree(_ROOT, second)
        yield first, second


def build_twice_and_compare(keep_wheel: Path | None) -> int:
    """Build this commit's wheel twice, from two directories, and compare.

    Args:
        keep_wheel: a directory to copy the first build's wheel into, or
            `None` to keep neither. The copy is taken before the second
            build runs, so that a build or a comparison that fails still
            leaves this image's half of an `--across-images` comparison
            behind.

    Returns:
        The process exit code: zero where the two builds agree.
    """
    with two_source_copies() as (first_source, second_source):
        root = first_source.parent

        first = build_wheel(first_source, root / "out-a")
        if keep_wheel is not None:
            keep_wheel.mkdir(parents=True, exist_ok=True)
            shutil.copy2(first, keep_wheel / first.name)
        second = build_wheel(second_source, root / "out-b")

        name = first.name
        complaints = diff_wheels(
            first,
            second,
            first_label="the first build",
            second_label="the second build",
        )

    if complaints:
        for complaint in complaints:
            print(f"::error::{complaint}", file=sys.stderr)
        return 1

    print(f"{name}: two builds of this commit agree, member for member")
    return 0


def build_repaired_twice_and_compare() -> int:
    """Build this commit through `cibuildwheel` twice, and compare.

    Returns:
        The process exit code: zero where the two builds produced the
        same wheels, name for name and member for member; one where
        `SOURCE_DATE_EPOCH` is unset, before either build runs.
    """
    if "SOURCE_DATE_EPOCH" not in os.environ:
        # not a default of "now": `auditwheel` and `delocate` would then
        # stamp each repair at the moment it ran, so two sequential
        # builds of one unchanged commit would disagree on `date_time`
        # for a reason that is not the wheel, and this entry point would
        # report that disagreement as a reproducibility defect rather
        # than as the caller's own missing step -- this module's own
        # docstring has the command that sets it
        print("SOURCE_DATE_EPOCH is not set", file=sys.stderr)
        return 1

    with two_source_copies() as (first_source, second_source):
        root = first_source.parent
        first = build_repaired_wheels(first_source, root / "out-a")
        second = build_repaired_wheels(second_source, root / "out-b")

        names = ", ".join(wheel.name for wheel in first)
        complaints = pair_wheels_by_name(
            first,
            second,
            first_label="the first build",
            second_label="the second build",
        )

    if complaints:
        for complaint in complaints:
            print(f"::error::{complaint}", file=sys.stderr)
        return 1

    print(f"{names}: two repaired builds of this commit agree, member for member")
    return 0


def main(argv: list[str]) -> int:
    """Run whichever of the comparisons the command line names."""
    if len(argv) == 3 and argv[1] == "--across-images":
        return compare_across_images(Path(argv[2]))
    if len(argv) == 3 and argv[1] == "--keep-wheel":
        return build_twice_and_compare(Path(argv[2]))
    if len(argv) == 2 and argv[1] == "--repaired":
        return build_repaired_twice_and_compare()
    if len(argv) != 1:
        print(
            f"usage: {argv[0]} [--keep-wheel DIR | --across-images DIR | --repaired]",
            file=sys.stderr,
        )
        return 2
    return build_twice_and_compare(None)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
