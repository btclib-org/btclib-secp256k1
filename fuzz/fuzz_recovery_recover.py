# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""An atheris harness over `btclib_secp256k1.recovery.recover`.

`recover` parses a compact signature and a recovery id through
`recovery.parse_compact`, so this reaches both. The input is read as one
flag octet, a 32-byte hash and a 64-byte signature, the last two
zero-padded: bits 0 and 1 of the flag are the recovery id and bit 2 is
`compressed`.

`ValueError` is what `recover` answers a signature with an `r` or an `s`
at or above the group order, or one from which no key is recovered, and
is swallowed below; anything else propagates as the finding it is.

The seed corpus is the first signature of `tests/ecdsa_sig.json` as `r
|| s`, with the recovery id for which a key is recovered.
"""

from __future__ import annotations

import contextlib
import sys

import atheris

from btclib_secp256k1 import recovery


def _take(data: bytes, start: int, size: int) -> bytes:
    """Return `size` octets of `data` from `start`, zero-padded if it ends."""
    return data[start : start + size].ljust(size, b"\0")


def arguments(data: bytes) -> tuple[bytes, bytes, int, bool]:
    """Split `data` into the arguments of `recover`."""
    flags = data[0] if data else 0
    return (_take(data, 1, 32), _take(data, 33, 64), flags & 3, bool(flags & 4))


def fuzz_target(data: bytes) -> None:
    """Recover the key `data` names.

    `ValueError` is swallowed as `recover`'s own refusal; any other
    exception propagates.
    """
    with contextlib.suppress(ValueError):
        recovery.recover(*arguments(data))


def main() -> None:
    """Wire `fuzz_target` to libFuzzer through atheris."""
    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_target, enable_python_coverage=True)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
