# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""An atheris harness over `btclib_secp256k1.keys.parse`.

`parse` is the parse every wrapper taking a public key begins with, and
it hands `secp256k1_ec_pubkey_parse` the octets and their length: every
prefix and coordinate the vendored parser accepts or refuses is reached
from a bare input, with no size check in front for a byte-oriented
fuzzer to spend its inputs on, which is what puts this entry point on
btclib-org/.github#342's list.

`ValueError` is what `parse` answers octets it refuses with, and is
swallowed below; anything else propagates as the finding it is.

The seed corpus is the generator point in its compressed and in its
uncompressed form.
"""

from __future__ import annotations

import contextlib
import sys

import atheris

from btclib_secp256k1 import keys


def fuzz_target(data: bytes) -> None:
    """Parse `data` as a public key, compressed or uncompressed.

    `ValueError` is swallowed as `parse`'s own refusal; any other
    exception propagates, which is how atheris tells a defect from the
    domain of input the bindings already refuse.
    """
    with contextlib.suppress(ValueError):
        keys.parse(data)


def main() -> None:
    """Wire `fuzz_target` to libFuzzer through atheris."""
    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_target, enable_python_coverage=True)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
