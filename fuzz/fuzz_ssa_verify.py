# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""An atheris harness over the key and signature of `ssa.verify`.

`fuzz_ssa_verify_message.py` fixes both and varies the message; here the
key and the signature vary and the message is the rest of the input.
`verify` takes the key as 32, 33 or 65 octets and the signature as 64.
The first octet picks the key's size, and the key and the signature are
read at their sizes, zero-padded, so that no input is spent on a size
check.

`ValueError` is what `verify` answers a key it refuses with, and is
swallowed below; anything else propagates as the finding it is. A
signature that does not verify is `False`, not an exception.

The seed corpus is BIP340 vector 0 of `tests/bip340_test_vectors.csv`.
"""

from __future__ import annotations

import contextlib
import sys

import atheris

from btclib_secp256k1 import ssa

KEY_SIZES = (32, 33, 65)
SIGNATURE_SIZE = 64


def _take(data: bytes, start: int, size: int) -> bytes:
    """Return `size` octets of `data` from `start`, zero-padded if it ends."""
    return data[start : start + size].ljust(size, b"\0")


def arguments(data: bytes) -> tuple[bytes, bytes, bytes]:
    """Split `data` into the message, the key and the signature of `verify`."""
    key_size = KEY_SIZES[(data[0] if data else 0) % len(KEY_SIZES)]
    signature_start = 1 + key_size
    return (
        data[signature_start + SIGNATURE_SIZE :],
        _take(data, 1, key_size),
        _take(data, signature_start, SIGNATURE_SIZE),
    )


def fuzz_target(data: bytes) -> None:
    """Verify the signature `data` carries, under the key it carries.

    `ValueError` is swallowed as `verify`'s own refusal; any other
    exception propagates.
    """
    with contextlib.suppress(ValueError):
        ssa.verify(*arguments(data))


def main() -> None:
    """Wire `fuzz_target` to libFuzzer through atheris."""
    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_target, enable_python_coverage=True)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
