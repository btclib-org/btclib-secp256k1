# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""BIP327's own vectors, run unchanged against `btclib_secp256k1.zkp.musig`.

The same files `tests/vectors_test.py` reads for
`btclib_secp256k1.musig` -- `tests/README.md` has their provenance, and
nothing here re-pins it. #607's own issue names this as the
API-compatibility check secp256k1-zkp#330 was opened to make possible:
zkp's `musig_pubkey_agg`, `nonce_agg`, `nonce_process` (over its own
five shared arguments, the adaptor left NULL) and `partial_sig_agg` are
BIP327's algorithm, so the same published values hold. What has no
vector here is the adaptor extension -- BIP327 does not define one --
which `tests/zkp_musig_test.py` checks by round trip instead.

Structured the same way as `tests/vectors_test.py`'s own musig section,
over `btclib_secp256k1.zkp.musig` rather than `btclib_secp256k1.musig`:
`musig_keyagg`, `musig_xonly` and `musig_tweaks` are that file's helpers
of the same name, unchanged in shape and rewritten only to call this
module's own `KeyAggCache`.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

pytest.importorskip("_btclib_secp256k1_zkp")

from btclib_secp256k1 import ssa, xonly
from btclib_secp256k1.zkp import musig

pytestmark = pytest.mark.zkp


def bip327_vectors(name: str) -> dict[str, Any]:
    """Read one of the BIP327 vector json files, vendored from bitcoin/bips."""
    path = pathlib.Path(__file__).parent / f"bip327_{name}_vectors.json"
    with path.open(encoding="utf-8") as json_file:
        loaded: dict[str, Any] = json.load(json_file)
        return loaded


def musig_keyagg(
    pubkeys_hex: list[str], tweaks: list[tuple[bytes, bool]]
) -> musig.KeyAggCache | None:
    """Aggregate keys and apply the tweaks, None where a step is refused.

    `tests/vectors_test.py`'s own `musig_keyagg`, over this module's
    `KeyAggCache` instead of `btclib_secp256k1.musig`'s.
    """
    try:
        cache = musig.KeyAggCache([bytes.fromhex(pubkey) for pubkey in pubkeys_hex])
        for tweak, is_xonly in tweaks:
            if is_xonly:
                cache.pubkey_xonly_tweak_add(tweak)
            else:
                cache.pubkey_ec_tweak_add(tweak)
    except ValueError:
        return None
    return cache


def musig_xonly(cache: musig.KeyAggCache) -> str:
    """Serialize the aggregate key of a cache, as BIP327 writes it.

    `cache.pubkey_get` answers plain bytes, so `xonly.from_pubkey` --
    mainline's own -- is safe to call on it: the module docstring's
    cross-ffi caution is about cffi structs crossing the boundary, and
    nothing here does.
    """
    pubkey_bytes = cache.pubkey_get(compressed=False)
    return xonly.from_pubkey(pubkey_bytes)[0].hex().upper()


def musig_tweaks(
    vectors: dict[str, Any], case: dict[str, Any]
) -> list[tuple[bytes, bool]]:
    """Pair each tweak of a case with the flag saying how it is applied."""
    return [
        (bytes.fromhex(vectors["tweaks"][index]), is_xonly)
        for index, is_xonly in zip(
            case.get("tweak_indices", []), case.get("is_xonly", []), strict=True
        )
    ]


KEY_AGG = bip327_vectors("key_agg")
NONCE_AGG = bip327_vectors("nonce_agg")
SIGN_VERIFY = bip327_vectors("sign_verify")
SIG_AGG = bip327_vectors("sig_agg")

# the same restriction tests/vectors_test.py applies, for the same
# reason: secp256k1_musig_nonce_process takes a msg32
SIGNABLE = [
    case
    for case in SIGN_VERIFY["valid_test_cases"]
    if len(bytes.fromhex(SIGN_VERIFY["msgs"][case["msg_index"]])) == 32
]


@pytest.mark.parametrize(
    "case", KEY_AGG["valid_test_cases"], ids=lambda c: c["expected"][:8]
)
def test_bip327_key_agg_vector(case: dict[str, Any]) -> None:
    """Aggregate the keys of one BIP327 vector into the key it publishes."""
    cache = musig_keyagg(
        [KEY_AGG["pubkeys"][i] for i in case["key_indices"]],
        musig_tweaks(KEY_AGG, case),
    )
    assert cache is not None
    assert musig_xonly(cache) == case["expected"]


@pytest.mark.parametrize(
    "case", KEY_AGG["error_test_cases"], ids=lambda c: c["comment"]
)
def test_bip327_key_agg_error_vector(case: dict[str, Any]) -> None:
    """Refuse a key aggregation BIP327 says has to fail."""
    assert (
        musig_keyagg(
            [KEY_AGG["pubkeys"][i] for i in case["key_indices"]],
            musig_tweaks(KEY_AGG, case),
        )
        is None
    )


@pytest.mark.parametrize(
    "case", NONCE_AGG["valid_test_cases"], ids=lambda c: c["expected"][:8]
)
def test_bip327_nonce_agg_vector(case: dict[str, Any]) -> None:
    """Aggregate public nonces into the 66 bytes BIP327 publishes."""
    pubnonces = [bytes.fromhex(NONCE_AGG["pnonces"][i]) for i in case["pnonce_indices"]]
    assert musig.nonce_agg(pubnonces).hex().upper() == case["expected"]


@pytest.mark.parametrize(
    "case", NONCE_AGG["error_test_cases"], ids=lambda c: c["comment"]
)
def test_bip327_nonce_agg_error_vector(case: dict[str, Any]) -> None:
    """Refuse a public nonce BIP327 says is invalid, at the parse."""
    pubnonces = [bytes.fromhex(NONCE_AGG["pnonces"][i]) for i in case["pnonce_indices"]]
    with pytest.raises(ValueError, match="public nonce"):
        musig.nonce_agg(pubnonces)


@pytest.mark.parametrize("case", SIGNABLE, ids=lambda c: c["expected"][:8])
def test_bip327_partial_sig_verify_vector(case: dict[str, Any]) -> None:
    """Verify the partial signature BIP327 publishes for one signer.

    `tests/vectors_test.py`'s own such test has the reason the signing
    direction cannot be driven from these vectors.
    """
    pubkeys = [SIGN_VERIFY["pubkeys"][i] for i in case["key_indices"]]
    cache = musig_keyagg(pubkeys, [])
    assert cache is not None

    aggnonce_bytes = bytes.fromhex(SIGN_VERIFY["aggnonces"][case["aggnonce_index"]])
    msg = bytes.fromhex(SIGN_VERIFY["msgs"][case["msg_index"]])
    session = musig.Session(aggnonce_bytes, msg, cache)

    signer = case["signer_index"]
    pubnonce_bytes = bytes.fromhex(
        SIGN_VERIFY["pnonces"][case["nonce_indices"][signer]]
    )
    partial_sig_bytes = bytes.fromhex(case["expected"])
    assert session.partial_sig_verify(
        partial_sig_bytes, pubnonce_bytes, bytes.fromhex(pubkeys[signer]), cache
    )


@pytest.mark.parametrize(
    "case", SIGN_VERIFY["verify_fail_test_cases"], ids=lambda c: c["comment"]
)
def test_bip327_partial_sig_verify_fail_vector(case: dict[str, Any]) -> None:
    """Refuse a partial signature BIP327 says does not verify."""
    pubkeys = [SIGN_VERIFY["pubkeys"][i] for i in case["key_indices"]]
    cache = musig_keyagg(pubkeys, [])
    assert cache is not None

    pubnonces = [
        bytes.fromhex(SIGN_VERIFY["pnonces"][i]) for i in case["nonce_indices"]
    ]
    aggnonce = musig.nonce_agg(pubnonces)
    msg = bytes.fromhex(SIGN_VERIFY["msgs"][case["msg_index"]])
    session = musig.Session(aggnonce, msg, cache)

    signer = case["signer_index"]
    # a signature out of range is refused by the parse; one in range and
    # wrong, by the verification
    try:
        verified = session.partial_sig_verify(
            bytes.fromhex(case["sig"]),
            pubnonces[signer],
            bytes.fromhex(pubkeys[signer]),
            cache,
        )
    except ValueError:
        return
    assert not verified


@pytest.mark.parametrize(
    "case", SIG_AGG["valid_test_cases"], ids=lambda c: c["expected"][:8]
)
def test_bip327_sig_agg_vector(case: dict[str, Any]) -> None:
    """Aggregate partial signatures into the BIP340 signature BIP327 gives."""
    cache = musig_keyagg(
        [SIG_AGG["pubkeys"][i] for i in case["key_indices"]],
        musig_tweaks(SIG_AGG, case),
    )
    assert cache is not None

    aggnonce_bytes = bytes.fromhex(case["aggnonce"])
    msg = bytes.fromhex(SIG_AGG["msg"])
    session = musig.Session(aggnonce_bytes, msg, cache)

    partial_sigs = [bytes.fromhex(SIG_AGG["psigs"][i]) for i in case["psig_indices"]]
    signature = session.partial_sig_agg(partial_sigs)
    assert signature.hex().upper() == case["expected"]
    # and it is a BIP340 signature of the aggregate key, tweaks included
    assert ssa.verify(msg, bytes.fromhex(musig_xonly(cache)), signature)


@pytest.mark.parametrize(
    "case", SIG_AGG["error_test_cases"], ids=lambda c: c["comment"]
)
def test_bip327_sig_agg_error_vector(case: dict[str, Any]) -> None:
    """Refuse a partial signature BIP327 says cannot be aggregated."""
    refused = 0
    for i in case["psig_indices"]:
        try:
            musig.partial_sig_parse(bytes.fromhex(SIG_AGG["psigs"][i]))
        except ValueError:
            refused += 1
    assert refused > 0
