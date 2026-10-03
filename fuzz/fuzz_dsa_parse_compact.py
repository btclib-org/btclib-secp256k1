# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""An atheris harness over `btclib_secp256k1.dsa.parse_compact`.

`parse_compact` proves two 32-byte scalars below the group order and
hands them to `secp256k1_ecdsa_signature_parse_compact`.

The harness reads exactly 64 octets, padded with zeros or cut, rather
than leaving the length to the fuzzer: a fixed-size entry point refuses
any other length before it parses, and a byte-oriented fuzzer would
spend nearly every input on that refusal.

`ValueError` is what `parse_compact` answers a signature with an `r` or
an `s` at or above the group order, and is swallowed below; anything
else propagates as the finding it is.

The seed corpus is the first signature of `tests/ecdsa_sig.json` as `r
|| s`.
"""

from __future__ import annotations

import contextlib
import sys

import atheris

from btclib_secp256k1 import dsa

SIZE = 64


def arguments(data: bytes) -> tuple[bytes]:
    """Return the 64 octets `parse_compact` is handed."""
    return (data[:SIZE].ljust(SIZE, b"\0"),)


def fuzz_target(data: bytes) -> None:
    """Parse `data` as a compact signature.

    `ValueError` is swallowed as `parse_compact`'s own refusal; any other
    exception propagates.
    """
    with contextlib.suppress(ValueError):
        dsa.parse_compact(*arguments(data))


def main() -> None:
    """Wire `fuzz_target` to libFuzzer through atheris."""
    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_target, enable_python_coverage=True)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
