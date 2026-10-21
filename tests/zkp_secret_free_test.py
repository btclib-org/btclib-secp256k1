# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""A refusal carries no secret: each zkp key, blind and nonce is fed one.

`tests/secret_free_refusals_test.py` explains the tables and holds the
mainline half. This file holds the same tables for the entry points that
exist only in the flagged build: `SCALARS` for a private key, a tweak, a
blinding factor, a decryption key and an adaptor secret, `ENTROPIES` for a
nonce or its randomness, `VALID_SECRETS`, and `PUBLIC_POSITIONS` for a
generator, a commitment, an opening, a public nonce, a partial signature,
an encryption key and an adaptor, `SECNONCES` for the native secret nonce,
and `BARE` for the lists of blinding factors. Its MuSig2 module is also
refused a spent secret nonce and one held with the wrong key.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

import pytest

pytest.importorskip("_btclib_secp256k1_zkp")

from btclib_secp256k1 import keys, zkp
from btclib_secp256k1.zkp import ecdsa_adaptor, ecdsa_s2c, generator, musig, rangeproof
from btclib_secp256k1.zkp.context import check

from .secret_free_refusals_test import (
    DRAWN,
    IN_PLAY,
    MSG,
    OTHER,
    PARSES,
    PUB,
    SECRET,
    SHAPES,
    TWEAK,
    WRONG,
    WRONG_ENTROPY,
    WRONG_SCALAR,
    N,
    assert_free,
    mismatched_nonce,
    own_copy,
    package_modules,
    partial_sign_with,
    refused,
    refused_anyhow,
    refused_in_public_position,
    secret_entry_points,
    secret_nonce_with,
    spellings,
    spent_nonce,
    untested,
    wrong_values_unchanged,  # noqa: F401  # an autouse fixture, here too
)

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.zkp

ENCKEY = keys.pubkey_from_prvkey(TWEAK)
NONCE = hashlib.sha256(b"btclib_secp256k1 zkp secret_free nonce").digest()
DATA = hashlib.sha256(b"btclib_secp256k1 zkp secret_free data").digest()
#: The secrets the calls here hold besides the value fed: the mainline
#: ones, the rangeproof nonce and the sign-to-contract data.
ZKP_IN_PLAY: list[str | bytes] = [*IN_PLAY, NONCE, DATA]
COMMIT = generator.pedersen_commit(OTHER, 5)
PROOF = rangeproof.sign(COMMIT, OTHER, NONCE, 5)
ADAPTOR_SIG = ecdsa_adaptor.encrypt(MSG, OTHER, ENCKEY)
SIG = ecdsa_adaptor.decrypt(TWEAK, ADAPTOR_SIG)
#: `SIG` with `r` moved by one: recovery writes the decryption key before it
#: finds that `r` does not match.
OFF_R_SIG = ((int.from_bytes(SIG[:32], "big") + 1) % N).to_bytes(32, "big") + SIG[32:]
CACHE = musig.KeyAggCache([PUB])
AGGNONCE = musig.nonce_agg([
    musig.nonce_gen(PUB, OTHER, msg32=MSG, keyagg_cache=CACHE).pubnonce
])


#: Each entry point that takes a private key, a tweak, a blinding factor, a
#: decryption key or an adaptor secret, by the position the secret is fed
#: in, with what a refusal calls it.
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
    "musig.SecretNonce.partial_sign": (
        "the private key must",
        lambda v: partial_sign_with(v, musig),
    ),
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
    "ecdsa_s2c.anti_exfil_host_commit": (
        "the rand32 must",
        ecdsa_s2c.anti_exfil_host_commit,
    ),
    "ecdsa_s2c.anti_exfil_sign": (
        "the host_data32 must",
        lambda v: ecdsa_s2c.anti_exfil_sign(MSG, OTHER, v),
    ),
    "ecdsa_s2c.anti_exfil_host_verify": (
        "the host_data32 must",
        lambda v: ecdsa_s2c.anti_exfil_host_verify(bytes(64), MSG, PUB, v, bytes(33)),
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

#: Each entry point that takes a native secret nonce.
SECNONCES: dict[str, Callable[[Any], object]] = {
    "musig.SecretNonce": lambda v: secret_nonce_with(v, musig),
}

#: Each parameter that takes a list of secrets, with the secret fed bare in
#: its place, at a length the call refuses. At a matching length these take
#: it as a list of one-byte factors (btclib-org/btclib-secp256k1#1229).
#: `pedersen_blind_sum`'s `blinds` takes it so at any length, as
#: btclib-org/btclib-secp256k1#1228 finds for `create_outputs`, so it is
#: not here.
BARE: dict[str, Callable[[Any], object]] = {
    "generator.pedersen_blind_generator_blind_sum generator_blinds": (
        lambda v: generator.pedersen_blind_generator_blind_sum(
            [5, 7], v, [OTHER, TWEAK], 1
        )
    ),
    "generator.pedersen_blind_generator_blind_sum blinding_factors": (
        lambda v: generator.pedersen_blind_generator_blind_sum(
            [5, 7], [OTHER, TWEAK], v, 1
        )
    ),
}

#: Each refusal that a good secret reaches: the call, and the secrets it
#: computes, which `ZKP_IN_PLAY` does not hold.
VALID_SECRETS: dict[str, tuple[Callable[[], object], list[str | bytes]]] = {
    "ecdsa_adaptor.decrypt of a bad adaptor signature": (
        lambda: ecdsa_adaptor.decrypt(SECRET, bytes(162)),
        [],
    ),
    "ecdsa_adaptor.recover from a signature with another r": (
        lambda: ecdsa_adaptor.recover(OFF_R_SIG, ADAPTOR_SIG, ENCKEY),
        [],
    ),
    "generator.pedersen_commit past the range": (
        lambda: generator.pedersen_commit(SECRET, 2**64),
        [],
    ),
    "rangeproof.sign of a value below its minimum": (
        lambda: rangeproof.sign(COMMIT, SECRET, NONCE, 5, min_value=7),
        [],
    ),
    "rangeproof.sign of a nonce for a message too long": (
        lambda: rangeproof.sign(COMMIT, OTHER, SECRET, 5, message=bytes(10000)),
        [],
    ),
    "rangeproof.rewind of another proof": (
        lambda: rangeproof.rewind(COMMIT, PROOF, SECRET),
        [],
    ),
    "musig.adapt of a bad pre-signature": (
        lambda: musig.adapt(b"\xff" * 64, SECRET, 0),
        [],
    ),
}


def test_every_entry_point_that_takes_a_secret_is_fed_one() -> None:
    """Read the parameters of the zkp API, and find each in a table."""
    found = {
        name.removeprefix("zkp."): taken
        for name, taken in secret_entry_points(package_modules(zkp)).items()
    }
    assert found["ecdsa_adaptor.encrypt"] == (["prvkey"], ["aux_rand32"])
    assert untested(found, SCALARS, {**ENTROPIES, **SECNONCES}) == []


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
    DRAWN.clear()
    exc = refused(lambda: call(value), (phrase,))
    assert_free(exc, [*spellings(value), *ZKP_IN_PLAY, *DRAWN])


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
    assert_free(exc, [*spellings(value), *ZKP_IN_PLAY])


@pytest.mark.parametrize("wrong", WRONG)
@pytest.mark.parametrize("entry", SECNONCES)
def test_a_wrong_secret_nonce_is_refused_without_quoting_it(
    entry: str, wrong: str
) -> None:
    """Feed the secret as the native secret nonce of a zkp signer.

    Args:
        entry: the entry point, by name.
        wrong: the way the secret is wrong, by name.
    """
    value = own_copy(WRONG[wrong])
    DRAWN.clear()
    exc = refused_anyhow(lambda: SECNONCES[entry](value))
    assert_free(exc, [*spellings(WRONG[wrong]), *ZKP_IN_PLAY, *DRAWN])


@pytest.mark.parametrize("wrong", WRONG_SCALAR)
@pytest.mark.parametrize("entry", BARE)
def test_a_secret_passed_bare_for_a_container_is_not_quoted(
    entry: str, wrong: str
) -> None:
    """Feed the secret where a list of blinding factors belongs.

    Args:
        entry: the entry point and parameter, by name.
        wrong: the way the secret is wrong, by name.
    """
    value = WRONG_SCALAR[wrong]
    exc = refused_anyhow(lambda: BARE[entry](value))
    assert_free(exc, [*spellings(value), *ZKP_IN_PLAY])


@pytest.mark.parametrize("case", VALID_SECRETS)
def test_a_refusal_a_good_secret_reaches_does_not_quote_it(case: str) -> None:
    """Refuse a call whose secret is a good one.

    Args:
        case: the refusal, by name.
    """
    call, secrets = VALID_SECRETS[case]
    with pytest.raises((TypeError, ValueError, RuntimeError)) as caught:
        call()
    assert_free(caught.value, [*secrets, *ZKP_IN_PLAY])


#: The ways a zkp MuSig2 signature is refused for its secret nonce.
NONCE_CASES: dict[str, Callable[[], tuple[BaseException, list[str | bytes]]]] = {
    "spent": lambda: spent_nonce(musig),
    "mismatched": lambda: mismatched_nonce(musig, check),
}


@pytest.mark.parametrize("case", NONCE_CASES)
def test_a_secret_nonce_refused_does_not_quote_the_nonce_or_the_key(
    case: str,
) -> None:
    """Refuse a signature with a spent nonce or the wrong key.

    Args:
        case: the way the signature is refused, by name.
    """
    exc, secrets = NONCE_CASES[case]()
    assert_free(exc, [*secrets, *ZKP_IN_PLAY])


#: Each public type of the zkp subpackage refused with the secret in its
#: place: the call, and what a refusal calls the position.
PUBLIC_POSITIONS: dict[str, tuple[Callable[[bytes], object], tuple[str, ...]]] = {
    "generator.parse": (
        generator.parse,
        ("invalid generator", "the generator must"),
    ),
    "generator.pedersen_commitment_parse": (
        generator.pedersen_commitment_parse,
        ("invalid Pedersen commitment", "the Pedersen commitment must"),
    ),
    "ecdsa_s2c.opening_parse": (
        ecdsa_s2c.opening_parse,
        ("invalid opening", "the opening must"),
    ),
    "musig.pubnonce_parse": (
        musig.pubnonce_parse,
        ("invalid public nonce", "the public nonce must"),
    ),
    "musig.aggnonce_parse": (
        musig.aggnonce_parse,
        ("invalid aggregate nonce", "the aggregate nonce must"),
    ),
    "musig.partial_sig_parse": (
        musig.partial_sig_parse,
        ("the partial signature must",),
    ),
    "ecdsa_adaptor.verify": (
        lambda v: ecdsa_adaptor.verify(ADAPTOR_SIG, PUB, MSG, v),
        ("invalid encryption key",),
    ),
    "ecdsa_adaptor.encrypt": (
        lambda v: ecdsa_adaptor.encrypt(MSG, OTHER, v),
        ("invalid encryption key",),
    ),
    "musig.Session": (
        lambda v: musig.Session(AGGNONCE, MSG, CACHE, v),
        ("invalid adaptor",),
    ),
    "rangeproof.verify": (
        lambda v: rangeproof.verify(v, PROOF),
        ("invalid commitment", "the commitment must"),
    ),
}


@pytest.mark.parametrize(
    "entry,shape",
    [
        (entry, shape)
        for entry in PUBLIC_POSITIONS
        for shape in SHAPES
        if (entry, shape) not in PARSES
    ],
)
def test_a_secret_where_a_public_value_belongs_is_not_quoted(
    entry: str, shape: str
) -> None:
    """Feed the secret in a public position of the zkp subpackage.

    Args:
        entry: the entry point, by name.
        shape: how the secret is cut to the public type, by name.
    """
    call, phrases = PUBLIC_POSITIONS[entry]
    refused_in_public_position(call, phrases, SHAPES[shape], ZKP_IN_PLAY)
