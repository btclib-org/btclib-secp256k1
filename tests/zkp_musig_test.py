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
import inspect
import secrets
from collections.abc import Callable

import pytest

pytest.importorskip("_btclib_secp256k1_zkp")

from btclib_secp256k1 import ffi, keys, ssa
from btclib_secp256k1.zkp import context as zkp_context
from btclib_secp256k1.zkp import musig

pytestmark = pytest.mark.zkp

PRVKEYS = [(1).to_bytes(32, "big"), (2).to_bytes(32, "big")]
PUBKEYS = [keys.pubkey_from_prvkey(prvkey) for prvkey in PRVKEYS]
MSG = hashlib.sha256(b"btclib_secp256k1 zkp musig").digest()
TWEAK = hashlib.sha256(b"btclib_secp256k1 zkp musig tweak").digest()


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


def imposter_secnonce(
    secnonces: list[musig.SecretNonce],
) -> musig.SecretNonce:
    """Pair the first signer's secret nonce with the second signer's public one.

    Every piece is real and none is forged: `partial_sign` signs with the
    secret nonce, and what it is then checked against is the public nonce
    the object holds, which here belongs to somebody else's secret nonce.

    Args:
        secnonces: the two signers' nonces, in `PRVKEYS` order.

    Returns:
        A `SecretNonce` sharing the first signer's secret memory.
    """
    held = secnonces[0]._secnonce
    assert held is not None
    return musig.SecretNonce(
        held, musig.pubnonce_parse(secnonces[1].pubnonce), secnonces[0]._pubkey
    )


def test_partial_sign_verifies_its_signature_unless_told_not_to() -> None:
    """A partial signature that does not verify is refused by default.

    The check is against the public nonce the `SecretNonce` holds, and
    that is what the mismatch here changes: the signature `partial_sign`
    makes is the first signer's own, valid under the first signer's public
    nonce and not under the second's -- both asserted below with the
    session's own `partial_sig_verify`, the library's verdict and not this
    package's. So the refusal is the check working, and `verify=False`
    is what skips it.
    """
    # named at the call site, as `dsa.sign`'s and `ssa.sign`'s is
    verify = inspect.signature(musig.SecretNonce.partial_sign).parameters["verify"]
    assert verify.kind is inspect.Parameter.KEYWORD_ONLY

    cache, secnonces, session = two_of_two_session()
    pubnonces = [secnonce.pubnonce for secnonce in secnonces]

    with pytest.raises(RuntimeError, match="does not verify"):
        imposter_secnonce(secnonces).partial_sign(PRVKEYS[0], cache, session)

    cache, secnonces, session = two_of_two_session()
    unverified = imposter_secnonce(secnonces).partial_sign(
        PRVKEYS[0], cache, session, verify=False
    )
    assert len(unverified) == 32
    assert not session.partial_sig_verify(unverified, pubnonces[1], PUBKEYS[0], cache)
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


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(lambda cache, **kw: cache.pubkey_get(**kw), id="pubkey_get"),
        pytest.param(
            lambda cache, **kw: cache.pubkey_ec_tweak_add(TWEAK, **kw),
            id="pubkey_ec_tweak_add",
        ),
        pytest.param(
            lambda cache, **kw: cache.pubkey_xonly_tweak_add(TWEAK, **kw),
            id="pubkey_xonly_tweak_add",
        ),
    ],
)
def test_key_agg_cache_answers_the_compressed_key_by_default(
    answer: Callable[..., bytes],
) -> None:
    """The 33 bytes are the default, and `compressed=False` is the 65.

    `compressed` says "whether to return 33 bytes rather than 65", so the
    default is the 33 and the 65 is the same point spelled out: what
    `keys.reserialize` makes of the one is the other. Each answer comes
    from a cache of its own, a tweak being applied to the cache it is
    made on.
    """
    default = answer(musig.KeyAggCache(PUBKEYS))
    explicit = answer(musig.KeyAggCache(PUBKEYS), compressed=True)
    uncompressed = answer(musig.KeyAggCache(PUBKEYS), compressed=False)

    assert len(default) == 33
    assert default == explicit
    assert len(uncompressed) == 65
    assert keys.reserialize(uncompressed, compressed=True) == default


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


def test_nonce_gen_counter_takes_the_whole_of_a_uint64() -> None:
    """The last counter a `uint64_t` holds is accepted.

    `secp256k1_musig_nonce_gen_counter` takes a `uint64_t`, so 2**64 - 1
    is the last value there is, and
    `test_nonce_gen_counter_needs_a_private_key_and_a_counter` refuses the
    one after it. A bound below it refuses a counter the signer this
    exists for is entitled to reach, and nothing shows that until it does.
    """
    for counter in (2**63, 2**64 - 2, 2**64 - 1):
        with musig.nonce_gen_counter(PRVKEYS[0], counter) as secnonce:
            assert len(secnonce.pubnonce) == 66


# the two ways to start a session, each called with only what it requires
NONCE_GENERATORS = [
    pytest.param(
        lambda **extra: musig.nonce_gen(PUBKEYS[0], PRVKEYS[0], **extra),
        id="nonce_gen",
    ),
    pytest.param(
        lambda **extra: musig.nonce_gen_counter(PRVKEYS[0], 0, **extra),
        id="nonce_gen_counter",
    ),
]
# the two optional 32-octet inputs of both, and what a refusal calls each
NONCE_INPUTS = [("msg32", "message"), ("extra_input32", "extra_input32")]


@pytest.mark.parametrize("size", [31, 33])
@pytest.mark.parametrize("argument, name", NONCE_INPUTS)
@pytest.mark.parametrize("generate", NONCE_GENERATORS)
def test_nonce_generation_refuses_an_input_of_the_wrong_width(
    generate: Callable[..., musig.SecretNonce], argument: str, name: str, size: int
) -> None:
    """`msg32` and `extra_input32` are 32 octets, and one either side is not.

    libsecp256k1-zkp reads exactly 32 octets from each through a bare
    pointer, so a shorter value is read past its end and a longer one is
    read in part.
    """
    with pytest.raises(ValueError, match=f"{name} must be 32 bytes"):
        generate(**{argument: bytes(size)})


@pytest.mark.parametrize("argument", [argument for argument, _ in NONCE_INPUTS])
@pytest.mark.parametrize("generate", NONCE_GENERATORS)
def test_nonce_generation_takes_an_input_of_32_octets(
    generate: Callable[..., musig.SecretNonce], argument: str
) -> None:
    """The width the refusals above are measured against is accepted."""
    with generate(**{argument: bytes(32)}) as secnonce:
        assert len(secnonce.pubnonce) == 66


def test_nonce_gen_asks_secrets_for_32_octets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The session randomness `nonce_gen` draws is 32 octets.

    BIP327 asks for 32 octets of it. What is drawn cannot show its length
    -- `session_secrand` is a 32-octet array a shorter draw fills in
    part, and the nonce that comes out is as good a nonce as any -- so
    this is the one thing that can hold it: what is asked of `secrets`,
    which is what `tests/core_test.py`'s
    `test_generated_randomness_is_always_32_octets` does for the modules
    an unflagged build has. The context is built first, that being a
    draw of its own and made on first use.
    """
    zkp_context._bindings()
    requested: list[int] = []
    real_token_bytes = secrets.token_bytes

    def recording(size: int) -> bytes:
        requested.append(size)
        return real_token_bytes(size)

    monkeypatch.setattr(secrets, "token_bytes", recording)

    musig.nonce_gen(PUBKEYS[0]).wipe()

    assert requested == [32]


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


def test_extract_adaptor_into_a_caller_s_buffer() -> None:
    """With `into` the adaptor lands there, not in a returned `bytes` (#640)."""
    sec_adaptor = hashlib.sha256(b"btclib_secp256k1 zkp musig adaptor into").digest()
    adaptor_point = keys.pubkey_from_prvkey(sec_adaptor)

    cache, secnonces, session = two_of_two_session(adaptor_bytes=adaptor_point)
    partial_sigs = [
        secnonce.partial_sign(prvkey, cache, session)
        for secnonce, prvkey in zip(secnonces, PRVKEYS, strict=True)
    ]
    pre_sig = session.partial_sig_agg(partial_sigs)
    parity = session.nonce_parity()
    signature = musig.adapt(pre_sig, sec_adaptor, parity)

    into = bytearray(32)
    assert musig.extract_adaptor(signature, pre_sig, parity, into=into) is None
    assert bytes(into) == sec_adaptor


def pin_the_draw(monkeypatch: pytest.MonkeyPatch, seed: int) -> None:
    """Make the session randomness of the next two `nonce_gen` calls `seed`'s.

    `two_of_two_session` draws it from `secrets`, one 32-octet draw per
    signer, and a session's nonce parity is decided by those two draws:
    left alone, the parity a test meets is whichever the draws gave, and
    a test may not rely on which.

    Args:
        monkeypatch: what the `secrets` function is replaced through.
        seed: which pair of draws; two seeds give two sessions.
    """
    zkp_context._bindings()  # its own draw, made on first use, is not one of these
    draws = iter(
        hashlib.sha256(
            b"btclib_secp256k1 zkp musig draw %d %d" % (seed, signer)
        ).digest()
        for signer in range(2)
    )
    monkeypatch.setattr(secrets, "token_bytes", lambda _size: next(draws))


# a seed of `pin_the_draw` for each parity the session can have, and the
# parity it was chosen for. `test_adaptor_round_trips_at_either_parity`
# asserts the parity before it uses it, so a library that derives its
# nonces differently fails there rather than testing one parity twice
PINNED_DRAWS = [pytest.param(0, 0, id="even"), pytest.param(1, 1, id="odd")]


@pytest.mark.parametrize("seed, parity", PINNED_DRAWS)
def test_adaptor_round_trips_at_either_parity(
    monkeypatch: pytest.MonkeyPatch, seed: int, parity: int
) -> None:
    """The adaptor round trip, with the nonce parity fixed rather than drawn.

    `adapt` and `extract_adaptor` take the parity of the session's
    aggregate nonce, 0 or 1, and a wrong one gives a signature that does
    not verify and an adaptor that is not the secret. `nonce_gen` draws
    its randomness from `secrets`, so `test_adaptor_round_trip` meets
    whichever parity the draws gave it; here the draws are pinned, once
    for each parity, and both parities are accepted.
    """
    pin_the_draw(monkeypatch, seed)
    sec_adaptor = hashlib.sha256(b"btclib_secp256k1 zkp musig adaptor").digest()
    adaptor_point = keys.pubkey_from_prvkey(sec_adaptor)

    cache, secnonces, session = two_of_two_session(adaptor_bytes=adaptor_point)
    partial_sigs = [
        secnonce.partial_sign(prvkey, cache, session)
        for secnonce, prvkey in zip(secnonces, PRVKEYS, strict=True)
    ]
    pre_sig = session.partial_sig_agg(partial_sigs)
    assert session.nonce_parity() == parity

    signature = musig.adapt(pre_sig, sec_adaptor, parity)
    assert ssa.verify(MSG, cache.agg_pubkey, signature)
    assert musig.extract_adaptor(signature, pre_sig, parity) == sec_adaptor

    # the other parity is in range, so it is answered and not refused, and
    # what it answers is wrong: it is the range that `adapt` and
    # `extract_adaptor` check, and the session is not theirs to see
    wrong = 1 - parity
    assert not ssa.verify(
        MSG, cache.agg_pubkey, musig.adapt(pre_sig, sec_adaptor, wrong)
    )
    assert musig.extract_adaptor(signature, pre_sig, wrong) != sec_adaptor


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


@pytest.mark.parametrize("nonce_parity", [-1, 2])
def test_extract_adaptor_refuses_a_nonce_parity_out_of_range(nonce_parity: int) -> None:
    """`nonce_parity` is 0 or 1 here too, and 2 is as far out as -1."""
    with pytest.raises(ValueError, match="nonce_parity"):
        musig.extract_adaptor(bytes(64), bytes(64), nonce_parity)


def test_a_call_made_through_lib_reports_through_zkp_context_check() -> None:
    """The raw path this module's own reasoning explains beside `musig`.

    `SecretNonce.partial_sign` answers its own `ValueError` for a reused
    secret nonce; a caller reaching zkp's `lib` directly instead gets a
    bare 0 and reads why with `btclib_secp256k1.zkp.context.check()`.
    """
    from btclib_secp256k1.zkp import context as zkp_context  # noqa: PLC0415

    ffi_, lib_, ctx_ = zkp_context._bindings()
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
