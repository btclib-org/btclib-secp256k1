# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""An atheris harness over `btclib_secp256k1.dsa.parse_der`.

A DER signature is variable-length nested type-length-value, read by
`secp256k1_ecdsa_signature_parse_der` from the octets and their length:
the shape a fuzzer was made for, and the one of these targets whose
input carries lengths of its own, which is why btclib-org/.github#342
calls it the strongest of them.

`ValueError` is what `parse_der` answers a malformed signature with, and
is swallowed below; anything else propagates as the finding it is.

The seed corpus is two signatures of `tests/ecdsa_sig.json`, their
trailing sighash octet stripped as `tests/vectors_test.py` strips it:
one whose `r` is 32 octets, and one whose `r` carries the leading zero
DER requires ahead of a high first octet.
"""

from __future__ import annotations

import contextlib
import sys

import atheris

from btclib_secp256k1 import dsa


def fuzz_target(data: bytes) -> None:
    """Parse `data` as a DER signature.

    `ValueError` is swallowed as `parse_der`'s own refusal; any other
    exception propagates, which is how atheris tells a defect from the
    domain of input the bindings already refuse.
    """
    with contextlib.suppress(ValueError):
        dsa.parse_der(data)


def main() -> None:
    """Wire `fuzz_target` to libFuzzer through atheris."""
    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_target, enable_python_coverage=True)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
