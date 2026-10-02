# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""An atheris harness over `btclib_secp256k1.musig.pubnonce_parse`.

`pubnonce_parse` reads a signer's public nonce, two points, from 66
octets handed to libsecp256k1 with no length beside them.

The harness reads exactly 66 octets, padded with zeros or cut, rather
than leaving the length to the fuzzer: a fixed-size entry point refuses
any other length before it parses, and a byte-oriented fuzzer would
spend nearly every input on that refusal.

`ValueError` is what `pubnonce_parse` answers a point it cannot read
with, and is swallowed below; anything else propagates as the finding it
is.

The seed corpus is the first public nonce of
`tests/bip327_nonce_agg_vectors.json`.
"""

from __future__ import annotations

import contextlib
import sys

import atheris

from btclib_secp256k1 import musig

SIZE = 66


def arguments(data: bytes) -> tuple[bytes]:
    """Return the 66 octets `pubnonce_parse` is handed."""
    return (data[:SIZE].ljust(SIZE, b"\0"),)


def fuzz_target(data: bytes) -> None:
    """Parse `data` as a signer's public nonce.

    `ValueError` is swallowed as `pubnonce_parse`'s own refusal; any other
    exception propagates.
    """
    with contextlib.suppress(ValueError):
        musig.pubnonce_parse(*arguments(data))


def main() -> None:
    """Wire `fuzz_target` to libFuzzer through atheris."""
    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_target, enable_python_coverage=True)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
