# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""An atheris harness over `btclib_secp256k1.dsa.verify`.

`verify` parses a public key and a signature, in DER or compact form,
and checks the signature over a 32-byte hash. The input is read as one
flag octet, the hash, the key and the signature, so that all of them
vary at once:

- bit 0 of the flag is `compact`, bit 1 is `normalize`, and bit 2 makes
  the key 65 octets rather than 33;
- the hash and the key are read at their sizes, zero-padded;
- the signature is the rest of the input, as DER at any length, or the
  first 64 octets of it, zero-padded, where `compact` is set.

`ValueError` is what `verify` answers a key or a signature it refuses
with, and is swallowed below; anything else propagates as the finding it
is. A signature that does not verify is `False`, not an exception.

The seed corpus is the first signature of `tests/ecdsa_sig.json` with
its key, once in DER and once as `r || s`.
"""

from __future__ import annotations

import contextlib
import sys

import atheris

from btclib_secp256k1 import dsa


def _take(data: bytes, start: int, size: int) -> bytes:
    """Return `size` octets of `data` from `start`, zero-padded if it ends."""
    return data[start : start + size].ljust(size, b"\0")


def arguments(data: bytes) -> tuple[bytes, bytes, bytes, bool, bool]:
    """Split `data` into the arguments of `verify`."""
    flags = data[0] if data else 0
    compact = bool(flags & 1)
    key_size = 65 if flags & 4 else 33
    signature = _take(data, 33 + key_size, 64) if compact else data[33 + key_size :]
    return (
        _take(data, 1, 32),
        _take(data, 33, key_size),
        signature,
        bool(flags & 2),
        compact,
    )


def fuzz_target(data: bytes) -> None:
    """Verify the signature `data` carries, under the key it carries.

    `ValueError` is swallowed as `verify`'s own refusal; any other
    exception propagates.
    """
    msg, pubkey, signature, normalize, compact = arguments(data)
    with contextlib.suppress(ValueError):
        dsa.verify(msg, pubkey, signature, normalize=normalize, compact=compact)


def main() -> None:
    """Wire `fuzz_target` to libFuzzer through atheris."""
    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_target, enable_python_coverage=True)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
