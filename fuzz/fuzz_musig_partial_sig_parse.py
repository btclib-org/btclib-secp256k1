# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""An atheris harness over `btclib_secp256k1.musig.partial_sig_parse`.

`partial_sig_parse` reads a partial signature, a scalar, from 32 octets
handed to libsecp256k1 with no length beside them.

The harness reads exactly 32 octets, padded with zeros or cut, rather
than leaving the length to the fuzzer: a fixed-size entry point refuses
any other length before it parses, and a byte-oriented fuzzer would
spend nearly every input on that refusal.

`ValueError` is what `partial_sig_parse` answers a scalar at or above
the curve order with, and is swallowed below; anything else propagates
as the finding it is.

The seed corpus is the first partial signature of
`tests/bip327_sig_agg_vectors.json`.
"""

from __future__ import annotations

import contextlib
import sys

import atheris

from btclib_secp256k1 import musig

SIZE = 32


def arguments(data: bytes) -> tuple[bytes]:
    """Return the 32 octets `partial_sig_parse` is handed."""
    return (data[:SIZE].ljust(SIZE, b"\0"),)


def fuzz_target(data: bytes) -> None:
    """Parse `data` as a partial signature.

    `ValueError` is swallowed as `partial_sig_parse`'s own refusal; any other
    exception propagates.
    """
    with contextlib.suppress(ValueError):
        musig.partial_sig_parse(*arguments(data))


def main() -> None:
    """Wire `fuzz_target` to libFuzzer through atheris."""
    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_target, enable_python_coverage=True)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
