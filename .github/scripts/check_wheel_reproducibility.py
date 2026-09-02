# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

r"""Build the wheel twice from one checkout and diff the two archives.

`btclib-org/btclib-secp256k1#439` asks whether a wheel this project
builds reproduces byte for byte. `#497` and `#498` answered that for
macOS, by hand, building twice and comparing; `#500` is the same
measurement made repeatable and reaching the platforms a laptop cannot.
This script is that measurement, `wheel-reproducibility.yml` is what
runs it on every platform the release builds a wheel on, and which
platforms answer green is that workflow's own output rather than a list
kept here.

A whole-archive digest says two wheels differ and nothing past that.
`#497`'s own reading of a difference this coarse -- which byte, in which
member, and why -- took a person an evening once the digests alone had
already said "no". This compares the two archives member by member
instead: which members are present, in which order, and for every
member both sides share, whether its bytes agree and whether its stored
`mtime`, permission bits and compression method do. A red run therefore
names a member and a field rather than a wheel.

Building twice needs no cleanup step of its own between the two calls.
`scripts/hatch_build.py`'s build hook removes `build/` wholesale before
it starts compiling, for every wheel target it is asked to build, so
the second `uv build --wheel` below starts from nothing the first one
left rather than from anything this script clears first -- which
running the two builds in this checkout confirms rather than assumes,
the two producing one digest wherever the platform already reproduces.

Run it from a checkout with the submodule initialized:

    uv run --no-project python \\
        .github/scripts/check_wheel_reproducibility.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

_UV = shutil.which("uv") or "uv"
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


def build_wheel(out_dir: Path) -> Path:
    """Build this project's wheel into `out_dir`, and return its path.

    Args:
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
        cwd=_ROOT,
        check=True,
    )
    wheels = sorted(out_dir.glob("*.whl"))
    if len(wheels) != 1:
        msg = f"expected exactly one wheel in {out_dir}, found {wheels}"
        raise RuntimeError(msg)
    return wheels[0]


def diff_wheels(first: Path, second: Path) -> list[str]:
    """Return one line per way the two wheels disagree, member by member.

    Args:
        first: one build's wheel.
        second: another build's wheel of the same checkout.

    Returns:
        An empty list where the two archives are indistinguishable member
        for member; otherwise one entry per difference, naming the member
        and, for a metadata disagreement, the field and both values.
    """
    complaints: list[str] = []
    with zipfile.ZipFile(first) as za, zipfile.ZipFile(second) as zb:
        names_a = [info.filename for info in za.infolist()]
        names_b = [info.filename for info in zb.infolist()]
        by_name_a = {info.filename: info for info in za.infolist()}
        by_name_b = {info.filename: info for info in zb.infolist()}

        only_in_a = [name for name in names_a if name not in by_name_b]
        only_in_b = [name for name in names_b if name not in by_name_a]
        if only_in_a:
            complaints.append(f"only in {first.name}: {only_in_a}")
        if only_in_b:
            complaints.append(f"only in {second.name}: {only_in_b}")

        shared = [name for name in names_a if name in by_name_b]
        if not only_in_a and not only_in_b and names_a != names_b:
            complaints.append(
                f"member order differs: {names_a} in {first.name}, "
                f"{names_b} in {second.name}"
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


def main(argv: list[str]) -> int:
    """Build the wheel twice and report whether the two archives agree."""
    if len(argv) != 1:
        print(f"usage: {argv[0]}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="wheel-reproducibility-") as tmp:
        root = Path(tmp)
        first = build_wheel(root / "a")
        second = build_wheel(root / "b")

        if first.name != second.name:
            print(
                f"::error::two builds of one checkout named the wheel "
                f"differently: {first.name} vs {second.name}",
                file=sys.stderr,
            )
            return 1

        complaints = diff_wheels(first, second)

    if complaints:
        for complaint in complaints:
            print(f"::error::{complaint}", file=sys.stderr)
        return 1

    print(f"{first.name}: two builds of this checkout agree, member for member")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
