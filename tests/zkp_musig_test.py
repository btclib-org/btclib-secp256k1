# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""`btclib_secp256k1.zkp.musig`: the session lifecycle, and the adaptor.

`tests/zkp_musig_vectors_test.py` holds this module to BIP327's own
vectors for the entry points it shares with mainline; what is left
here is the session lifecycle -- the same split `tests/musig_test.py`
makes for `btclib_secp256k1.musig` -- and the entry points BIP327
has no vector for: `Session.nonce_parity`, `adapt` and
`extract_adaptor`. BIP327 defines no adaptor extension, and zkp's own
tests draw the adaptor secret with `testrand256` rather than from a
fixed vector (btclib-org/btclib#1051 checked and found nothing to lift), so the
adaptor path is checked by round trip instead: pre-sign, adapt with a
known secret, extract the secret back out of the two signatures.
"""

from __future__ import annotations

import gc
import hashlib

import pytest

pytest.importorskip("_btclib_secp256k1_zkp")

from btclib_secp256k1 import ffi, keys, ssa
from btclib_secp256k1.zkp import musig

pytestmark = pytest.mark.zkp

PRVKEYS = [(1).to_bytes(32, "big"), (2).to_bytes(32, "big")]
PUBKEYS = [keys.pubkey_from_prvkey(prvkey) for prvkey in PRVKEYS]
MSG = hashlib.sha256(b"btclib_secp256k1 zkp musig").digest()


def secnonce_memory(secnonce: musig.SecretNonce) -> bytes:
    """Return the octets of the secret nonce a `SecretNonce` holds.

    `tests/musig_test.py`'s own `secnonce_memory`, unchanged: `ffi` is
    mainline's, and `ffi.buffer` is cross-ffi safe over any cdata --
    `btclib_secp256k1.zkp.musig`'s own module docstring measured that.
    """
    held = secnonce._secnonce
    return b"" if held is None else bytes(ffi.buffer(held))


def two_of_two_session(
    adaptor_bytes: bytes | None = None,
) -> tuple[musig.KeyAggCache, list[musig.SecretNonce], musig.Session]:
    """Build a 2-of-2 key aggregation, nonces and session, up to round two.

    Args:
        adaptor_bytes: an adaptor point, if this session is a
            pre-signature one.

    Returns:
        The key aggregation, one `SecretNonce` per signer in `PRVKEYS`
        order, and the session `partial_sign` and `partial_sig_verify`
        are checked against.
    """
    cache = musig.KeyAggCache(PUBKEYS)
    secnonces = [
        musig.nonce_gen(pubkey, prvkey, msg32=MSG, keyagg_cache=cache)
        for prvkey, pubkey in zip(PRVKEYS, PUBKEYS, strict=True)
    ]
    aggnonce = musig.nonce_agg([secnonce.pubnonce for secnonce in secnonces])
    session = musig.Session(aggnonce, MSG, cache, adaptor_bytes)
    return cache, secnonces, session


def test_a_2_of_2_session_signs_and_verifies() -> None:
    """The usage example: aggregate, two rounds, and a plain BIP340 check."""
    cache, secnonces, session = two_of_two_session()
    pubnonces = [secnonce.pubnonce for secnonce in secnonces]

    partial_sigs = [
        secnonce.partial_sign(prvkey, cache, session)
        for secnonce, prvkey in zip(secnonces, PRVKEYS, strict=True)
    ]
    for partial_sig, pubnonce, pubkey in zip(
        partial_sigs, pubnonces, PUBKEYS, strict=True
    ):
        assert session.partial_sig_verify(partial_sig, pubnonce, pubkey, cache)

    signature = session.partial_sig_agg(partial_sigs)
    assert len(signature) == 64
    assert ssa.verify(MSG, cache.agg_pubkey, signature)


def test_partial_sign_without_verify_answers_the_same_signature() -> None:
    """`verify=False` skips the check and not the arithmetic."""
    cache, secnonces, session = two_of_two_session()
    unverified = secnonces[0].partial_sign(PRVKEYS[0], cache, session, verify=False)
    assert session.partial_sig_verify(
        unverified, secnonces[0].pubnonce, PUBKEYS[0], cache
    )


def test_key_agg_cache_requires_at_least_one_key() -> None:
    """An empty sequence has no aggregate to compute."""
    with pytest.raises(ValueError, match="at least one public key"):
        musig.KeyAggCache([])


def test_key_agg_cache_reports_which_key_failed_to_parse() -> None:
    """The index of the bad key, not just that the aggregation failed."""
    with pytest.raises(ValueError, match="public key at index 1"):
        musig.KeyAggCache([PUBKEYS[0], b"\x00" * 33])


def test_nonce_agg_requires_at_least_one_pubnonce() -> None:
    """An empty sequence has no aggregate to compute."""
    with pytest.raises(ValueError, match="at least one public nonce"):
        musig.nonce_agg([])


def test_nonce_agg_reports_which_pubnonce_failed_to_parse() -> None:
    """The index of the bad nonce, as the key aggregation test has above."""
    _cache, secnonces, _session = two_of_two_session()
    with pytest.raises(ValueError, match="public nonce at index 1"):
        musig.nonce_agg([secnonces[0].pubnonce, bytes(66)])


def test_partial_sig_agg_requires_at_least_one_signature() -> None:
    """An empty sequence has no signature to aggregate."""
    _cache, _secnonces, session = two_of_two_session()
    with pytest.raises(ValueError, match="at least one partial signature"):
        session.partial_sig_agg([])


def test_partial_sig_agg_reports_which_signature_failed_to_parse() -> None:
    """The index of the bad signature, for the reason above."""
    cache, secnonces, session = two_of_two_session()
    good = secnonces[0].partial_sign(PRVKEYS[0], cache, session)
    with pytest.raises(ValueError, match="partial signature at index 1"):
        session.partial_sig_agg([good, b"\xff" * 32])


def test_key_agg_cache_tweaks_leave_agg_pubkey_alone() -> None:
    """`agg_pubkey` is BIP327's `Q`, fixed at construction, tweaks or not."""
    tweak = hashlib.sha256(b"btclib_secp256k1 zkp musig tweak").digest()
    ec_cache = musig.KeyAggCache(PUBKEYS)
    before = ec_cache.agg_pubkey
    untweaked = ec_cache.pubkey_get()

    ec_tweaked = ec_cache.pubkey_ec_tweak_add(tweak)
    assert ec_cache.agg_pubkey == before
    assert ec_cache.pubkey_get() == ec_tweaked
    assert ec_tweaked != untweaked

    xonly_cache = musig.KeyAggCache(PUBKEYS)
    xonly_tweaked = xonly_cache.pubkey_xonly_tweak_add(tweak)
    assert xonly_cache.agg_pubkey == before
    assert xonly_tweaked != untweaked


def test_key_agg_cache_tweak_add_refuses_an_invalid_tweak() -> None:
    """A tweak that is the wrong length, or does not fit in 32 bytes."""
    cache = musig.KeyAggCache(PUBKEYS)
    with pytest.raises(ValueError, match="32 bytes"):
        cache.pubkey_ec_tweak_add(b"\x01" * 31)
    # 2**256 - 1, above the curve order: not a valid scalar
    with pytest.raises(ValueError, match="invalid tweak"):
        cache.pubkey_xonly_tweak_add(b"\xff" * 32)


def test_session_refuses_an_invalid_aggregate_nonce() -> None:
    """A wrong-length or unparsable aggregate nonce is refused at the parse."""
    cache = musig.KeyAggCache(PUBKEYS)
    with pytest.raises(ValueError, match="66 bytes"):
        musig.Session(bytes(65), MSG, cache)
    # 0x02 names no valid point at x = 0
    with pytest.raises(ValueError, match="invalid aggregate nonce"):
        musig.Session(b"\x02" + bytes(65), MSG, cache)


def test_session_refuses_a_message_of_the_wrong_length() -> None:
    """`nonce_process` signs a 32-byte message, `msg32` being its own name."""
    cache, secnonces, _session = two_of_two_session()
    aggnonce = musig.nonce_agg([secnonce.pubnonce for secnonce in secnonces])
    with pytest.raises(ValueError, match="message"):
        musig.Session(aggnonce, MSG + b"\x00", cache)


def test_session_refuses_an_invalid_adaptor() -> None:
    """The adaptor point is parsed exactly as any other public key."""
    cache, secnonces, _session = two_of_two_session()
    aggnonce = musig.nonce_agg([secnonce.pubnonce for secnonce in secnonces])
    with pytest.raises(ValueError, match="invalid adaptor"):
        musig.Session(aggnonce, MSG, cache, bytes(33))


def test_partial_sig_verify_answers_false_for_a_wrong_signature() -> None:
    """A partial signature attributed to the wrong signer does not verify."""
    cache, secnonces, session = two_of_two_session()
    sig0 = secnonces[0].partial_sign(PRVKEYS[0], cache, session)
    assert not session.partial_sig_verify(
        sig0, secnonces[1].pubnonce, PUBKEYS[1], cache
    )


def test_partial_sign_refuses_a_mismatched_private_key() -> None:
    """A secnonce signs only for the keypair `nonce_gen` built it for."""
    cache, secnonces, session = two_of_two_session()
    with pytest.raises(ValueError, match="do not match this secret nonce"):
        secnonces[0].partial_sign(PRVKEYS[1], cache, session)
    assert secnonce_memory(secnonces[0]) == b""


def test_partial_sign_wipes_the_secret_nonce_even_when_keypair_raises() -> None:
    """A private key `keypair` refuses spends the nonce just the same."""
    cache, secnonces, session = two_of_two_session()
    with pytest.raises(ValueError, match="private key"):
        secnonces[0].partial_sign(0, cache, session)
    assert secnonce_memory(secnonces[0]) == b""
    with pytest.raises(ValueError, match="wiped or already spent"):
        secnonces[0].partial_sign(PRVKEYS[0], cache, session)


def test_a_wiped_secret_nonce_refuses_to_sign() -> None:
    """Rather than signing with the zeros the wipe left."""
    cache, secnonces, session = two_of_two_session()
    secnonces[0].wipe()
    with pytest.raises(ValueError, match="wiped or already spent"):
        secnonces[0].partial_sign(PRVKEYS[0], cache, session)


def test_wipe_overwrites_the_secret_nonce() -> None:
    """The secret is in there until `wipe`, and gone after it."""
    secnonce = musig.nonce_gen(PUBKEYS[0], PRVKEYS[0])
    assert secnonce_memory(secnonce) != b""

    secnonce.wipe()
    assert secnonce_memory(secnonce) == b""


def test_partial_sign_wipes_the_secret_nonce_it_spends() -> None:
    """`partial_sign` wipes on the way out, whether it signs or is refused."""
    cache, secnonces, session = two_of_two_session()
    secnonces[0].partial_sign(PRVKEYS[0], cache, session)
    assert secnonce_memory(secnonces[0]) == b""


def test_the_with_block_wipes_whatever_ended_it() -> None:
    """A signature, and an exception, leave the same wiped secret nonce."""
    cache, secnonces, session = two_of_two_session()
    with secnonces[0] as secnonce:
        secnonce.partial_sign(PRVKEYS[0], cache, session)
    assert secnonce_memory(secnonces[0]) == b""

    raising = musig.nonce_gen(PUBKEYS[0], PRVKEYS[0])
    with pytest.raises(ValueError, match="what the block raised"), raising:
        raise ValueError("what the block raised")
    assert secnonce_memory(raising) == b""


def test_wiping_twice_is_not_an_error() -> None:
    """Signing consumes it, and wiping afterwards is not a mistake to report."""
    cache, secnonces, session = two_of_two_session()
    with secnonces[0] as secnonce:
        secnonce.partial_sign(PRVKEYS[0], cache, session)
    secnonces[0].wipe()
    assert secnonce_memory(secnonces[0]) == b""


def test_a_dropped_secret_nonce_leaves_the_memory_as_it_was() -> None:
    """Nothing wipes behind a caller who neither wipes nor uses `with`."""
    secnonce = musig.nonce_gen(PUBKEYS[0], PRVKEYS[0])
    # kept alive here, and by nothing else once the secnonce is dropped
    held = secnonce._secnonce
    assert held is not None
    before = bytes(ffi.buffer(held))
    assert before != bytes(len(before))

    del secnonce
    gc.collect()  # refcounting has dropped it already; PyPy needs asking

    assert bytes(ffi.buffer(held)) == before


def test_nonce_gen_needs_only_a_public_key() -> None:
    """Every other argument is optional, and folds into the derivation."""
    secnonce = musig.nonce_gen(PUBKEYS[0])
    assert len(secnonce.pubnonce) == 66
    secnonce.wipe()


def test_nonce_gen_refuses_an_invalid_public_key() -> None:
    """The public key is parsed before any secret is generated."""
    with pytest.raises(ValueError, match="public key"):
        musig.nonce_gen(bytes(33))


# secp256k1 group order
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


@pytest.mark.parametrize("prvkey", [0, N])
def test_nonce_gen_refuses_a_private_key_out_of_range(prvkey: int) -> None:
    """The one way `secp256k1_musig_nonce_gen` can fail given valid octets."""
    with pytest.raises(ValueError, match="private key"):
        musig.nonce_gen(PUBKEYS[0], prvkey)


def test_nonce_gen_counter_needs_a_private_key_and_a_counter() -> None:
    """The alternative to `nonce_gen`, for a signer counting instead."""
    secnonce = musig.nonce_gen_counter(PRVKEYS[0], 0)
    assert len(secnonce.pubnonce) == 66
    secnonce.wipe()

    with pytest.raises(ValueError, match="nonrepeating_cnt"):
        musig.nonce_gen_counter(PRVKEYS[0], -1)
    with pytest.raises(ValueError, match="nonrepeating_cnt"):
        musig.nonce_gen_counter(PRVKEYS[0], 2**64)
    with pytest.raises(TypeError, match="nonrepeating_cnt"):
        musig.nonce_gen_counter(PRVKEYS[0], 1.0)  # type: ignore[arg-type]


def test_pubnonce_aggnonce_and_partial_sig_round_trip() -> None:
    """`parse` and `serialize` answer each other, for all three types."""
    cache, secnonces, session = two_of_two_session()
    pubnonce = musig.pubnonce_parse(secnonces[0].pubnonce)
    assert musig.pubnonce_serialize(pubnonce) == secnonces[0].pubnonce

    aggnonce_bytes = musig.nonce_agg([s.pubnonce for s in secnonces])
    aggnonce = musig.aggnonce_parse(aggnonce_bytes)
    assert musig.aggnonce_serialize(aggnonce) == aggnonce_bytes

    partial_sig_bytes = secnonces[0].partial_sign(PRVKEYS[0], cache, session)
    partial_sig = musig.partial_sig_parse(partial_sig_bytes)
    assert musig.partial_sig_serialize(partial_sig) == partial_sig_bytes


def test_nonce_parity_of_a_plain_session() -> None:
    """`nonce_parity` reads off any session, an adaptor one or not."""
    _cache, _secnonces, session = two_of_two_session()
    assert session.nonce_parity() in (0, 1)


def test_adaptor_round_trip() -> None:
    """Pre-sign, adapt with the secret, extract the secret back out.

    BIP327 has no vector for this, and zkp's own tests draw the adaptor
    secret with `testrand256` rather than from a published value -- the
    module docstring and #607's own issue give the reason. What is
    checked instead is the construction itself: the pre-signature does
    not verify on its own, the adapted one does, and `extract_adaptor`
    recovers the exact secret `adapt` was given.
    """
    sec_adaptor = hashlib.sha256(b"btclib_secp256k1 zkp musig adaptor").digest()
    adaptor_point = keys.pubkey_from_prvkey(sec_adaptor)

    cache, secnonces, session = two_of_two_session(adaptor_bytes=adaptor_point)
    partial_sigs = [
        secnonce.partial_sign(prvkey, cache, session)
        for secnonce, prvkey in zip(secnonces, PRVKEYS, strict=True)
    ]
    pre_sig = session.partial_sig_agg(partial_sigs)
    parity = session.nonce_parity()

    assert not ssa.verify(MSG, cache.agg_pubkey, pre_sig)

    signature = musig.adapt(pre_sig, sec_adaptor, parity)
    assert ssa.verify(MSG, cache.agg_pubkey, signature)

    extracted = musig.extract_adaptor(signature, pre_sig, parity)
    assert extracted == sec_adaptor


def test_adapt_refuses_an_overflowing_argument() -> None:
    """`adapt` fails on a pre-signature or secret adaptor that overflows."""
    with pytest.raises(ValueError, match="invalid pre-signature or secret adaptor"):
        musig.adapt(b"\xff" * 64, b"\xff" * 32, 0)


def test_adapt_refuses_a_pre_signature_of_the_wrong_length() -> None:
    """`pre_sig64` is 64 bytes, `octets` being what enforces it."""
    with pytest.raises(ValueError, match="64 bytes"):
        musig.adapt(bytes(63), bytes(32), 0)


def test_extract_adaptor_refuses_an_overflowing_argument() -> None:
    """`extract_adaptor` fails on a signature or pre-signature that overflow."""
    with pytest.raises(ValueError, match="invalid signature or pre-signature"):
        musig.extract_adaptor(b"\xff" * 64, b"\xff" * 64, 0)


def test_extract_adaptor_refuses_a_signature_of_the_wrong_length() -> None:
    """`sig64` and `pre_sig64` are 64 bytes each."""
    with pytest.raises(ValueError, match="64 bytes"):
        musig.extract_adaptor(bytes(63), bytes(64), 0)


@pytest.mark.parametrize("nonce_parity", [-1, 2])
def test_adapt_refuses_a_nonce_parity_out_of_range(nonce_parity: int) -> None:
    """`nonce_parity` is 0 or 1, `Session.nonce_parity`'s own range."""
    with pytest.raises(ValueError, match="nonce_parity"):
        musig.adapt(bytes(64), bytes(32), nonce_parity)


def test_a_call_made_through_lib_reports_through_zkp_context_check() -> None:
    """The raw path this module's own reasoning explains beside `musig`.

    `SecretNonce.partial_sign` answers its own `ValueError` for a reused
    secret nonce; a caller reaching zkp's `lib` directly instead gets a
    bare 0 and reads why with `btclib_secp256k1.zkp.context.check()`.
    """
    from btclib_secp256k1.zkp import context as zkp_context  # noqa: PLC0415
    from btclib_secp256k1.zkp.musig import _boundary  # noqa: PLC0415

    ffi_, lib_, ctx_ = _boundary()
    cache, secnonces, session = two_of_two_session()
    secnonce = secnonces[0]._secnonce
    keypair_obj = ffi_.new("secp256k1_keypair *")
    assert lib_.secp256k1_keypair_create(ctx_, keypair_obj, PRVKEYS[0])
    partial_sig = ffi_.new("secp256k1_musig_partial_sig *")
    assert lib_.secp256k1_musig_partial_sign(
        ctx_, partial_sig, secnonce, keypair_obj, cache._cache_(), session._session_()
    )
    secnonces[0]._secnonce = None  # the C call already zeroed it

    assert not lib_.secp256k1_musig_partial_sign(
        ctx_, partial_sig, secnonce, keypair_obj, cache._cache_(), session._session_()
    )
    with pytest.raises(ValueError, match="secnonce_magic"):
        zkp_context.check()
