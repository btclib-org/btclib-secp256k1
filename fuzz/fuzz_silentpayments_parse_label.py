# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""An atheris harness over `btclib_secp256k1.silentpayments.parse_label`.

A label is a compressed point, so reading one is a field square root in
the vendored library, handed 33 octets with no length beside them.

The harness reads exactly 33 octets, padded with zeros or cut, rather
than leaving the length to the fuzzer: a fixed-size entry point refuses
any other length before it parses, and a byte-oriented fuzzer would
spend nearly every input on that refusal.

`ValueError` is what `parse_label` answers octets that are not a point
with, and is swallowed below; anything else propagates as the finding it
is.

The seed corpus is the scan public key of the first sending vector of
`tests/bip352_send_and_receive_test_vectors.json`, which is a point.
"""

from __future__ import annotations

import contextlib
import sys

import atheris

from btclib_secp256k1 import silentpayments

SIZE = 33


def arguments(data: bytes) -> tuple[bytes]:
    """Return the 33 octets `parse_label` is handed."""
    return (data[:SIZE].ljust(SIZE, b"\0"),)


def fuzz_target(data: bytes) -> None:
    """Parse `data` as a label.

    `ValueError` is swallowed as `parse_label`'s own refusal; any other
    exception propagates.
    """
    with contextlib.suppress(ValueError):
        silentpayments.parse_label(*arguments(data))


def main() -> None:
    """Wire `fuzz_target` to libFuzzer through atheris."""
    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_target, enable_python_coverage=True)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
