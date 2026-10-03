# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""An atheris harness over `btclib_secp256k1.ellswift.decode`.

Every 64 octets decode to a point, and `decode` has nothing to refuse:
the one thing a stranger chooses is 64 octets that reach a field
inversion and a square root in the vendored library.

The harness reads the 64 octets after the first, padded with zeros or
cut, rather than leaving the length to the fuzzer: a fixed-size entry
point refuses any other length before it parses, and a byte-oriented
fuzzer would spend nearly every input on that refusal.

The first octet is `compressed`, by its bit 0.

Nothing is suppressed. With the size fixed `decode` raises for no input,
so every exception is a finding.

The seed corpus is the second row of
`tests/bip324_ellswift_decode_test_vectors.csv`.
"""

from __future__ import annotations

import sys

import atheris

from btclib_secp256k1 import ellswift

SIZE = 64


def arguments(data: bytes) -> tuple[bytes, bool]:
    """Split `data` into the arguments of `decode`."""
    return data[1 : 1 + SIZE].ljust(SIZE, b"\0"), bool(data[0] & 1) if data else True


def fuzz_target(data: bytes) -> None:
    """Decode the 64 octets `data` carries.

    Every exception propagates: there is no expected failure to tell a
    defect from.
    """
    ellswift.decode(*arguments(data))


def main() -> None:
    """Wire `fuzz_target` to libFuzzer through atheris."""
    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_target, enable_python_coverage=True)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
