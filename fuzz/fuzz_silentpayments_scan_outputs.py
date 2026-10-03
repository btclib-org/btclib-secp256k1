# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""An atheris harness over `btclib_secp256k1.silentpayments.scan_outputs`.

`scan_outputs` takes the outputs of a transaction, which a stranger
chose, and the prevouts summary of its inputs, which may come from a
stranger too: `SUMMARY_SIZE` octets, an outpoint and a compressed public
key, refused unless the key is on the curve. The input is read as one
flag octet, the scan private key, the summary, the spend public key, the
outputs and a label with its tweak, each zero-padded. Bits 0 and 1 of
the flag make the outputs 1 to 4 in number, bit 2 makes the spend public
key 65 octets rather than 33, and bit 3 gives the call a label cache
holding the label and the tweak the input ends with.

`ValueError` is what `scan_outputs` answers an argument it refuses with,
and is swallowed below; anything else propagates as the finding it is.

The seed corpus is the first receiving vector of
`tests/bip352_send_and_receive_test_vectors.json`. BIP352 publishes no
summary, so the seed's is `prevouts_summary` of that vector's input
public keys and first outpoint.
"""

from __future__ import annotations

import contextlib
import sys

import atheris

from btclib_secp256k1 import silentpayments

SUMMARY_SIZE = silentpayments.SUMMARY_SIZE


def _take(data: bytes, start: int, size: int) -> bytes:
    """Return `size` octets of `data` from `start`, zero-padded if it ends."""
    return data[start : start + size].ljust(size, b"\0")


def arguments(
    data: bytes,
) -> tuple[list[bytes], bytes, bytes, bytes, dict[bytes, bytes] | None]:
    """Split `data` into the arguments of `scan_outputs`."""
    flags = data[0] if data else 0
    count = 1 + flags % 4
    spend_size = 65 if flags & 4 else 33
    scan_prvkey = _take(data, 1, 32)
    summary = _take(data, 33, SUMMARY_SIZE)
    spend_start = 33 + SUMMARY_SIZE
    outputs_start = spend_start + spend_size
    label_start = outputs_start + 32 * count
    labels = (
        {_take(data, label_start, 33): _take(data, label_start + 33, 32)}
        if flags & 8
        else None
    )
    return (
        [_take(data, outputs_start + 32 * i, 32) for i in range(count)],
        scan_prvkey,
        summary,
        _take(data, spend_start, spend_size),
        labels,
    )


def fuzz_target(data: bytes) -> None:
    """Scan the outputs `data` carries, for the key and the summary it carries.

    `ValueError` is swallowed as `scan_outputs`'s own refusal; any other
    exception propagates.
    """
    with contextlib.suppress(ValueError):
        silentpayments.scan_outputs(*arguments(data))


def main() -> None:
    """Wire `fuzz_target` to libFuzzer through atheris."""
    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_target, enable_python_coverage=True)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
