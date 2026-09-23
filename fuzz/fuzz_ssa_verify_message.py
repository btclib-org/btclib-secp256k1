# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""An atheris harness over the message of `btclib_secp256k1.ssa.verify`.

BIP340 signs a message of any length, and `verify` hands it to
`secp256k1_schnorrsig_verify` with its length beside it: the message is
what a stranger chose and the one unsized argument of `verify`, which
is what puts it on btclib-org/.github#342's list.
The key and the signature are fixed to vector 18 of
`tests/bip340_test_vectors.csv`, so the message is all that varies, and
the seed is that vector's own message: `verify` answers True there and
False to every mutation of it.

Nothing is suppressed. `verify` raises only for a signature that is not
64 octets or a key that is not a point, and both are fixed here, so
every exception is a finding.
"""

from __future__ import annotations

import sys

import atheris

from btclib_secp256k1 import ssa

# vector 18 of tests/bip340_test_vectors.csv, as hex so that
# tests/fuzz_corpus_test.py reads them off this file's source without
# importing it: atheris above is pre-installed in ClusterFuzzLite's image
# and declared in no dependency group here
PUBKEY = bytes.fromhex(
    "778CAA53B4393AC467774D09497A87224BF9FAB6F6E68B23086497324D6FD117"
)
SIGNATURE = bytes.fromhex(
    "403B12B0D8555A344175EA7EC746566303321E5DBFA8BE6F091635163ECA79A8"
    "585ED3E3170807E7C03B720FC54C7B23897FCBA0E9D0B4A06894CFD249F22367"
)


def fuzz_target(data: bytes) -> None:
    """Verify the fixed signature over `data` as the message.

    Every exception propagates: with the key and the signature fixed,
    `verify` has no refusal left for the message, so there is no
    expected failure to tell a defect from.
    """
    ssa.verify(data, PUBKEY, SIGNATURE)


def main() -> None:
    """Wire `fuzz_target` to libFuzzer through atheris."""
    atheris.instrument_all()
    atheris.Setup(sys.argv, fuzz_target, enable_python_coverage=True)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
