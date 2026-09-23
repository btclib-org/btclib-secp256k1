# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""An atheris harness over `btclib_secp256k1.hashes.tagged_sha256`.

The BIP340 tagged hash takes a tag and a message of any length, each
handed to `secp256k1_tagged_sha256` with its length beside it. The tag
is a protocol's constant and the message is what a stranger chose, so
the tag is fixed to BIP340's challenge tag and the message is what
varies, which is what puts this entry point on
btclib-org/.github#342's list.

Nothing is suppressed. `tagged_sha256` raises only where the vendored
call fails, which no input can make it do, so every exception is a
finding.

The seed corpus is what BIP340's challenge hashes under this tag for
vector 0 of `tests/bip340_test_vectors.csv`: the signature's first
half, the public key and the message.
"""

from __future__ import annotations

import sys

import atheris

from btclib_secp256k1 import hashes

TAG = b"BIP0340/challenge"


def fuzz_target(data: bytes) -> None:
    """Hash `data` as the message under the fixed tag.

    Every exception propagates: `tagged_sha256` refuses no octets, so
    there is no expected failure to tell a defect from.
    """
    hashes.tagged_sha256(TAG, data)


def main() -> None:
    """Wire `fuzz_target` to libFuzzer through atheris."""
    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_target, enable_python_coverage=True)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
