# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""An atheris harness over `btclib_secp256k1.ellswift.xdh`.

`xdh` takes two 64-octet encodings and a private key, and hashes the
shared point with BIP324's function. The input is read as one flag
octet, the two encodings and the key, each zero-padded: bit 0 of the
flag is the party.

`ValueError` is what `xdh` answers a private key that is not a valid
scalar with, and is swallowed below; anything else propagates as the
finding it is.

The seed corpus is the first two rows of
`tests/bip324_ellswift_decode_test_vectors.csv` as the two encodings,
with the private key 1.
"""

from __future__ import annotations

import contextlib
import sys

import atheris

from btclib_secp256k1 import ellswift


def _take(data: bytes, start: int, size: int) -> bytes:
    """Return `size` octets of `data` from `start`, zero-padded if it ends."""
    return data[start : start + size].ljust(size, b"\0")


def arguments(data: bytes) -> tuple[bytes, bytes, bytes, int]:
    """Split `data` into the arguments of `xdh`."""
    return (
        _take(data, 1, 64),
        _take(data, 65, 64),
        _take(data, 129, 32),
        (data[0] if data else 0) & 1,
    )


def fuzz_target(data: bytes) -> None:
    """Compute the shared secret of the two keys `data` carries.

    `ValueError` is swallowed as `xdh`'s own refusal; any other
    exception propagates.
    """
    with contextlib.suppress(ValueError):
        ellswift.xdh(*arguments(data))


def main() -> None:
    """Wire `fuzz_target` to libFuzzer through atheris."""
    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_target, enable_python_coverage=True)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
