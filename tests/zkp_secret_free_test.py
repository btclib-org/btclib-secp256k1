# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""A refusal carries no secret: the zkp subpackage, fed every secret it takes.

`tests/secret_free_refusals_test.py` explains the tables and holds the
mainline half. This file is the same for the entry points that exist only
in the flagged build: a private key, a blinding factor, a nonce, the
secret of an adaptor and the nonces of a MuSig2 session.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

import pytest

pytest.importorskip("_btclib_secp256k1_zkp")

from btclib_secp256k1 import ffi, keys, zkp
from btclib_secp256k1.zkp import ecdsa_adaptor, ecdsa_s2c, generator, musig, rangeproof
from btclib_secp256k1.zkp.context import check

from .secret_free import assert_secret_free
from .secret_free_refusals_test import (
    MSG,
    OTHER,
    PUB,
    SECRET,
    TWEAK,
    WRONG_ENTROPY,
    WRONG_SCALAR,
    package_modules,
    refused,
    secret_entry_points,
    spellings,
    untested,
)

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.zkp

ENCKEY = keys.pubkey_from_prvkey(TWEAK)
NONCE = hashlib.sha256(b"btclib_secp256k1 zkp secret_free nonce").digest()
DATA = hashlib.sha256(b"btclib_secp256k1 zkp secret_free data").digest()
COMMIT = generator.pedersen_commit(OTHER, 5)
PROOF = rangeproof.sign(COMMIT, OTHER, NONCE, 5)
ADAPTOR_SIG = ecdsa_adaptor.encrypt(MSG, OTHER, ENCKEY)


def two_of_two_session() -> tuple[
    musig.KeyAggCache, list[musig.SecretNonce], musig.Session
]:
    """Build a 2-of-2 session in which the secret is the first signer's key.

    Returns:
        The key aggregation, each signer's secret nonce, and the session.
    """
    prvkeys = [SECRET, OTHER]
    pubkeys = [keys.pubkey_from_prvkey(prvkey) for prvkey in prvkeys]
    cache = musig.KeyAggCache(pubkeys)
    secnonces = [
        musig.nonce_gen(pubkey, prvkey, msg32=MSG, keyagg_cache=cache)
        for prvkey, pubkey in zip(prvkeys, pubkeys, strict=True)
    ]
    aggnonce = musig.nonce_agg([secnonce.pubnonce for secnonce in secnonces])
    return cache, secnonces, musig.Session(aggnonce, MSG, cache)


def partial_sign_with(prvkey: Any) -> bytes:
    """Sign for the first signer of a fresh 2-of-2 session.

    Args:
        prvkey: the private key to sign with.

    Returns:
        The partial signature.
    """
    cache, secnonces, session = two_of_two_session()
    return secnonces[0].partial_sign(prvkey, cache, session)


def nonce_memory(secnonce: musig.SecretNonce) -> bytes:
    """Return the octets of the secret nonce a `SecretNonce` holds.

    Args:
        secnonce: the nonce, not yet spent.

    Returns:
        Its octets.
    """
    held = secnonce._secnonce
    assert held is not None
    return bytes(ffi.buffer(held))


def spent_nonce() -> tuple[BaseException, list[str | bytes]]:
    """Sign twice with one secret nonce, and return the second refusal.

    Returns:
        The refusal, and the secrets that were in play: the key and the
        nonce.
    """
    cache, secnonces, session = two_of_two_session()
    memory = nonce_memory(secnonces[0])
    assert any(memory)
    secnonces[0].partial_sign(SECRET, cache, session)
    with pytest.raises(ValueError, match="already spent") as caught:
        secnonces[0].partial_sign(SECRET, cache, session)
    return caught.value, [SECRET, memory]


def mismatched_nonce() -> tuple[BaseException, list[str | bytes]]:
    """Sign with the second signer's key and the first signer's nonce.

    Returns:
        The refusal, and the secrets that were in play: both keys and the
        nonce.
    """
    cache, secnonces, session = two_of_two_session()
    memory = nonce_memory(secnonces[0])
    assert any(memory)
    with pytest.raises(ValueError, match="do not match") as caught:
        secnonces[0].partial_sign(OTHER, cache, session)
    # the mismatch is an ARG_CHECK that recorded an illegal argument on this
    # thread; read here so that no later test raises it
    with pytest.raises(ValueError, match="secp256k1_fe_equal") as recorded:
        check()
    assert_secret_free(recorded.value, [SECRET, OTHER, memory])
    return caught.value, [SECRET, OTHER, memory]


#: Each entry point that takes a private key, a blinding factor or an
#: adaptor secret, by the position the secret is fed in, with what a
#: refusal calls it.
SCALARS: dict[str, tuple[str, Callable[[Any], object]]] = {
    "ecdsa_adaptor.encrypt": (
        "the private key must",
        lambda v: ecdsa_adaptor.encrypt(MSG, v, ENCKEY),
    ),
    "ecdsa_adaptor.decrypt": (
        "the decryption key must",
        lambda v: ecdsa_adaptor.decrypt(v, ADAPTOR_SIG),
    ),
    "ecdsa_s2c.sign": ("the private key must", lambda v: ecdsa_s2c.sign(MSG, v, DATA)),
    "ecdsa_s2c.anti_exfil_signer_commit": (
        "the private key must",
        lambda v: ecdsa_s2c.anti_exfil_signer_commit(MSG, v, DATA),
    ),
    "ecdsa_s2c.anti_exfil_sign": (
        "the private key must",
        lambda v: ecdsa_s2c.anti_exfil_sign(MSG, v, DATA),
    ),
    "generator.generate_blinded": (
        "the blind32 must",
        lambda v: generator.generate_blinded(DATA, v),
    ),
    "generator.pedersen_commit": (
        "the blind must",
        lambda v: generator.pedersen_commit(v, 5),
    ),
    "generator.pedersen_blind_sum": (
        "the blinding factor at index 0 must",
        lambda v: generator.pedersen_blind_sum([v, OTHER], 1),
    ),
    "generator.pedersen_blind_generator_blind_sum generator_blinds": (
        "the generator blind at index 0 must",
        lambda v: generator.pedersen_blind_generator_blind_sum(
            [5, 7], [v, OTHER], [OTHER, TWEAK], 1
        ),
    ),
    "generator.pedersen_blind_generator_blind_sum blinding_factors": (
        "the blinding factor at index 0 must",
        lambda v: generator.pedersen_blind_generator_blind_sum(
            [5, 7], [OTHER, TWEAK], [v, OTHER], 1
        ),
    ),
    "rangeproof.sign": (
        "the blind must",
        lambda v: rangeproof.sign(COMMIT, v, NONCE, 5),
    ),
    "musig.nonce_gen": ("the private key must", lambda v: musig.nonce_gen(PUB, v)),
    "musig.nonce_gen_counter": (
        "the private key must",
        lambda v: musig.nonce_gen_counter(v, 1),
    ),
    "musig.SecretNonce.partial_sign": ("the private key must", partial_sign_with),
    "musig.adapt": ("the secret adaptor must", lambda v: musig.adapt(bytes(64), v, 0)),
    "musig.KeyAggCache.pubkey_ec_tweak_add": (
        "the tweak must",
        lambda v: musig.KeyAggCache([PUB]).pubkey_ec_tweak_add(v),
    ),
    "musig.KeyAggCache.pubkey_xonly_tweak_add": (
        "the tweak must",
        lambda v: musig.KeyAggCache([PUB]).pubkey_xonly_tweak_add(v),
    ),
}

#: Each entry point that takes a nonce or the entropy of one.
ENTROPIES: dict[str, tuple[str, Callable[[Any], object]]] = {
    "ecdsa_adaptor.encrypt": (
        "the aux_rand32 must",
        lambda v: ecdsa_adaptor.encrypt(MSG, OTHER, ENCKEY, aux_rand32=v),
    ),
    "rangeproof.sign": (
        "the nonce must",
        lambda v: rangeproof.sign(COMMIT, OTHER, v, 5),
    ),
    "rangeproof.rewind": (
        "the nonce must",
        lambda v: rangeproof.rewind(COMMIT, PROOF, v),
    ),
    "musig.nonce_gen": (
        "the extra_input32 must",
        lambda v: musig.nonce_gen(PUB, OTHER, extra_input32=v),
    ),
    "musig.nonce_gen_counter": (
        "the extra_input32 must",
        lambda v: musig.nonce_gen_counter(OTHER, 1, extra_input32=v),
    ),
}

#: Each refusal that a good secret reaches: the call, and the secrets in
#: play.
VALID_SECRETS: dict[str, tuple[Callable[[], object], list[str | bytes]]] = {
    "ecdsa_adaptor.decrypt of a bad adaptor signature": (
        lambda: ecdsa_adaptor.decrypt(SECRET, bytes(162)),
        [SECRET],
    ),
    "ecdsa_adaptor.recover from another signature": (
        lambda: ecdsa_adaptor.recover(bytes(64), ADAPTOR_SIG, ENCKEY),
        [OTHER, TWEAK],
    ),
    "generator.pedersen_commit past the range": (
        lambda: generator.pedersen_commit(SECRET, 2**64),
        [SECRET],
    ),
    "rangeproof.sign of a value below its minimum": (
        lambda: rangeproof.sign(COMMIT, SECRET, NONCE, 5, min_value=7),
        [SECRET, NONCE],
    ),
    "rangeproof.sign of a nonce for a message too long": (
        lambda: rangeproof.sign(COMMIT, OTHER, SECRET, 5, message=bytes(10000)),
        [SECRET],
    ),
    "rangeproof.rewind of another proof": (
        lambda: rangeproof.rewind(COMMIT, PROOF, SECRET),
        [SECRET],
    ),
    "musig.adapt of a bad pre-signature": (
        lambda: musig.adapt(b"\xff" * 64, SECRET, 0),
        [SECRET],
    ),
}


def test_every_entry_point_that_takes_a_secret_is_fed_one() -> None:
    """Read the parameters of the zkp API, and find each in a table."""
    found = {
        name.removeprefix("zkp."): taken
        for name, taken in secret_entry_points(package_modules(zkp)).items()
    }
    assert "ecdsa_adaptor.encrypt" in found
    assert untested(found, SCALARS, ENTROPIES) == []


#: What the refusal of a key or a blind at the order says, by entry point. A
#: few say nothing of the argument: they are this package's message for a
#: call libsecp256k1 failed.
KEY = "invalid private key: not in [1, n-1]"
TWEAKED = "invalid tweak or resulting public key"
ORDER = {
    "ecdsa_adaptor.encrypt": KEY,
    "ecdsa_adaptor.decrypt": "invalid decryption key or adaptor signature",
    "ecdsa_s2c.sign": KEY,
    "ecdsa_s2c.anti_exfil_signer_commit": KEY,
    "ecdsa_s2c.anti_exfil_sign": KEY,
    "generator.generate_blinded": "invalid blind32, or seed generation failed",
    "generator.pedersen_commit": "Pedersen commitment failed",
    "generator.pedersen_blind_sum": "blinding factor sum failed",
    "generator.pedersen_blind_generator_blind_sum generator_blinds": (
        "blinding factor correction failed"
    ),
    "generator.pedersen_blind_generator_blind_sum blinding_factors": (
        "blinding factor correction failed"
    ),
    "rangeproof.sign": "rangeproof signing failed",
    "musig.nonce_gen": KEY,
    "musig.nonce_gen_counter": KEY,
    "musig.SecretNonce.partial_sign": KEY,
    "musig.adapt": "invalid pre-signature or secret adaptor",
    "musig.KeyAggCache.pubkey_ec_tweak_add": TWEAKED,
    "musig.KeyAggCache.pubkey_xonly_tweak_add": TWEAKED,
}


@pytest.mark.parametrize("wrong", WRONG_SCALAR)
@pytest.mark.parametrize("entry", SCALARS)
def test_a_wrong_private_key_is_refused_without_quoting_it(
    entry: str, wrong: str
) -> None:
    """Feed the secret as the wrong private key or blinding factor.

    Args:
        entry: the entry point, by name.
        wrong: the way the secret is wrong, by name.
    """
    label, call = SCALARS[entry]
    value = WRONG_SCALAR[wrong]
    phrase = ORDER[entry] if wrong == "at the order" else label
    exc = refused(lambda: call(value), (phrase,))
    assert_secret_free(exc, spellings(value))


@pytest.mark.parametrize("wrong", WRONG_ENTROPY)
@pytest.mark.parametrize("entry", ENTROPIES)
def test_a_wrong_nonce_is_refused_without_quoting_it(entry: str, wrong: str) -> None:
    """Feed the secret as the wrong nonce or entropy.

    Args:
        entry: the entry point, by name.
        wrong: the way the secret is wrong, by name.
    """
    label, call = ENTROPIES[entry]
    value = WRONG_ENTROPY[wrong]
    exc = refused(lambda: call(value), (label,))
    assert_secret_free(exc, spellings(value))


@pytest.mark.parametrize("case", VALID_SECRETS)
def test_a_refusal_a_good_secret_reaches_does_not_quote_it(case: str) -> None:
    """Refuse a call whose secret is a good one.

    Args:
        case: the refusal, by name.
    """
    call, secrets = VALID_SECRETS[case]
    with pytest.raises((TypeError, ValueError, RuntimeError)) as caught:
        call()
    assert_secret_free(caught.value, secrets)


@pytest.mark.parametrize("case", [spent_nonce, mismatched_nonce])
def test_a_secret_nonce_refused_does_not_quote_the_nonce_or_the_key(
    case: Callable[[], tuple[BaseException, list[str | bytes]]],
) -> None:
    """Refuse a signature with a spent nonce or the wrong key.

    Args:
        case: the way the signature is refused.
    """
    exc, secrets = case()
    assert_secret_free(exc, secrets)
