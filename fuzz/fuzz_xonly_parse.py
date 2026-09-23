# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""An atheris harness over `btclib_secp256k1.xonly.parse`.

`parse` takes a public key in any of its three serializations and hands
the 32-byte one to `secp256k1_xonly_pubkey_parse`, which is given a
pointer and no length: the `len != 32` test in front of it is this
package's own line and the whole of what stands between a caller's
octets and an overread in the vendored library. The 33- and 65-byte
forms reach a parser of their own behind it, so every length is a real
parse rather than a size check for a byte-oriented fuzzer to spend its
inputs on, which is what puts this entry point on
btclib-org/.github#342's list.

`ValueError` is what `parse` answers octets it refuses with, and is
swallowed below; anything else propagates. A precondition the vendored
library rejects comes back as a return code the wrapper turns into that
same `ValueError` rather than as an abort, `scripts/cffi_build.py`
compiling callbacks that return, so a crash under the address-sanitized
build this runs in is a memory finding.

The seed corpus is the generator point as its x coordinate and in its
uncompressed form, the two lengths that take different paths in.
"""

from __future__ import annotations

import contextlib
import sys

import atheris

from btclib_secp256k1 import xonly


def fuzz_target(data: bytes) -> None:
    """Parse `data` as a public key, in whichever of its forms it is.

    `ValueError` is swallowed as `parse`'s own refusal; any other
    exception propagates, which is how atheris tells a defect from the
    domain of input the bindings already refuse.
    """
    with contextlib.suppress(ValueError):
        xonly.parse(data)


def main() -> None:
    """Wire `fuzz_target` to libFuzzer through atheris."""
    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_target, enable_python_coverage=True)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
