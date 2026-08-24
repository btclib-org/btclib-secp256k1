# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Rewrite an sdist's member `mtime` to `SOURCE_DATE_EPOCH`.

Unlike the siblings' script, this one touches one field and not five.
Hatchling's sdist writer already stamps every member's ownership at
`uid`/`gid` `0` and `uname`/`gname` `""`, measurable with
`tarfile.getmembers()` against a build of this tree, so rewriting them
again would not change a byte. Mode is not rewritten at all: each
member's mode is the executable bit git tracks for that file, `0o755`
for `secp256k1/autogen.sh` and the small set of vendored tools beside
it, `0o644` for everything else, and flattening that to one constant
would strip the bit a plain `tar -x` of the archive needs to run them.

`mtime` is the field left. Hatchling's sdist writer reads
`SOURCE_DATE_EPOCH` when it is set and falls back to a fixed constant,
`1580601600`, when it is not -- neither is the tagged commit's own
date, which is what this script writes instead. Measured by building
this tree twice, once with the variable unset and once set to an
arbitrary second:

    uv build --sdist -o a && SOURCE_DATE_EPOCH=1000000000 \
      uv build --sdist -o b && shasum -a 256 a/* b/*

answers with one digest per build, agreeing on every field but `mtime`,
which is the one this script moves to the commit's own date rather than
either of hatchling's two choices. RELEASING.md's "Rebuild a release
from its tag" runs this script for that reason: skip it there and the
rebuild's `mtime` disagrees with the published archive.

What is *in* the archive, and every other member attribute, is already
this repository's own; only `mtime` is rewritten here, on every member
including directories, and the gzip header carries the same timestamp
instead of the moment it was compressed.

Run it after the sdist is built and before anything reads dist/:

    uv run --no-project --python 3.14 \
        .github/scripts/normalize_sdist.py dist/

RELEASING.md has the command that verifies a published release against a
rebuild of its tag.
"""

from __future__ import annotations

import gzip
import io
import os
import sys
import tarfile
from pathlib import Path


def normalize(archive: Path, epoch: int) -> None:
    """Rewrite one archive in place, every member's `mtime` at `epoch`."""
    members: list[tuple[tarfile.TarInfo, bytes | None]] = []
    with tarfile.open(archive, "r:gz") as source:
        for member in source.getmembers():
            # extractfile returns None for anything that is not a regular
            # file, a directory member being one of them
            stream = source.extractfile(member) if member.isfile() else None
            members.append((member, stream.read() if stream is not None else None))

    tar = io.BytesIO()
    with tarfile.open(fileobj=tar, mode="w", format=tarfile.PAX_FORMAT) as target:
        for member, content in members:
            member.mtime = epoch
            # the record a sub-second mtime would need: mtime becomes an
            # integer above, so none of the members this script has ever
            # met need one, but a stale record from the source archive
            # would otherwise survive the rewrite unexamined. Reassigned
            # rather than popped from in place: the attribute is typed as
            # a Mapping, immutable to a type checker even though it is a
            # dict at runtime
            member.pax_headers = {
                key: value
                for key, value in member.pax_headers.items()
                if key != "mtime"
            }
            target.addfile(member, io.BytesIO(content) if content is not None else None)

    compressed = io.BytesIO()
    # mtime, not the clock, and filename empty: gzip stores both in its
    # header, and the name of a temporary file is not the archive's
    with gzip.GzipFile(
        filename="", mode="wb", fileobj=compressed, mtime=epoch, compresslevel=9
    ) as compressor:
        compressor.write(tar.getvalue())
    archive.write_bytes(compressed.getvalue())


def main(argv: list[str]) -> int:
    """Normalize every sdist in the directory named on the command line."""
    if len(argv) != 2:
        print(f"usage: {argv[0]} <dist directory>", file=sys.stderr)
        return 2

    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch is None:
        # not a default of "now": a default would make the failure a
        # reproducibility bug found by whoever tried to verify a release,
        # which is the one person who cannot fix it
        print("SOURCE_DATE_EPOCH is not set", file=sys.stderr)
        return 1

    archives = sorted(Path(argv[1]).glob("*.tar.gz"))
    if not archives:
        print(f"no sdist in {argv[1]}", file=sys.stderr)
        return 1

    for archive in archives:
        normalize(archive, int(epoch))
        print(f"normalized {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
