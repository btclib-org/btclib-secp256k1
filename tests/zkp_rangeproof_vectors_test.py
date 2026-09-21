# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""`zkp.rangeproof` against the real library and its own fixed vectors.

Every test here is marked `zkp`, for the reason
`tests/zkp_generator_vectors_test.py`'s own module docstring gives.

`VECTOR_1`, `VECTOR_2` and `VECTOR_3` and everything named beside them
are lifted byte for byte from
`secp256k1-zkp/src/modules/rangeproof/tests_impl.h`'s own
`test_rangeproof_fixed_vectors`: a proof with no embedded message, one
with an embedded message, and a single-value proof of `2**64 - 1`. Two
of the three rewind there with the nonce set to the commitment's own raw
internal representation (`pc.data`), which is "implementation defined"
in `secp256k1_generator.h`'s own words and not something this package
exposes -- so `test_vector_1_verifies` and `test_vector_2_verifies` only
check `verify`, the half of the C test that needs no such nonce, and
`test_vector_3_round_trips` is the one that also drives `rewind`, its
own nonce being an ordinary 32 bytes rather than a struct's memory.

The property test below is `ISS 608
<https://github.com/btclib-org/btclib-secp256k1/issues/608>`_'s own
"sign -> verify -> rewind ... both exponents, with and without
min_value", quoted as the issue's own shorthand rather than a count of
this test's own parametrization: `test_sign_verify_rewind_round_trips`
is parametrized over three values of `exp` (`-1`, a single-value proof;
`0`; and `4`) crossed with two of `min_value`.

`BORROMEAN_*` below is not lifted from the header: `ISS 828
<https://github.com/btclib-org/btclib-secp256k1/issues/828>`_'s own body
has the reason -- `secp256k1_borromean_sign` stays internal, and
`test_borromean_internal`, the one C test that draws a signature, prints
nothing, so no fixed vector exists anywhere to transcribe. The tuple is
one accepted call captured from a temporary `fprintf` inserted into
`test_borromean_verify_api_internal`
(`src/modules/rangeproof/tests_impl.h`, in the fork this issue's own
submodule pin points at) and triple-verified before being written here:
the original C test run confirming it, a standalone C program linking
the same build confirming it a second way, and a raw `lib` call through
this package's own cffi binding confirming it a third.
"""

from __future__ import annotations

import secrets

import pytest

pytest.importorskip("_btclib_secp256k1_zkp")

from btclib_secp256k1.zkp import generator as g
from btclib_secp256k1.zkp import rangeproof as r

pytestmark = pytest.mark.zkp

VECTOR_1 = bytes.fromhex(
    "62070000000000000056022a5c420e1d51e1b7f36904b5bb9b416614f3644226e3a76a06bba8"
    "5a496f1976fbe5757788aba9664480ea29957fdf724aaf02bedd5d15d8aeff74c98c1a670eb2"
    "572299c321466f15580edbe66ec40dfe6f046b0d183d784098564ee44a7490a7ac9c16e03e81"
    "af0fe34f349952f7a7f6d383a0174b2da7d4fdf78445c411713d4a2234099ca7e5c8ba04bffd"
    "25117da44345c7629e7b80f609bb1b2ef3cd23e0ed814342bec49f588a0d6679097011683d87"
    "381c3c85525b62f73e7e87a29924d07d18635648a43afe65faa4d067aa98654de422754552e8"
    "41c7ed38ebf50290c945a3b04d03d7ab43e421fc83d6121d76b13c67631f529dc3235c4ea68d"
    "014aba9af4165b67c8e1d2426ddfcd086a73416ac284c631be57cb0edebf71d58af724b2a789"
    "96624fd9f7c3de4cab1372b4b3350482a8751dde46a80db823440044fa536c2dced3a680a120"
    "cad163bbbe395f9d2769b3331fdbda670537be65e97ea9c3ff378ab42dfef21685c70fd9be14"
    "d180149f58569841f626f7a27166b47a9c1273d3df772b49e5ca5057446e3f5856bc21704fc6"
    "aa12ff7ca73ded46c140e658092adab376ab44b54eb312e0268a52ac491de706533a0135212e"
    "8648c575c1a27d2253f63f41c5b3087da367c0bbb68df0d30172d36382011ae71d22fa9533f6"
    "f2dea25386555ab42e7575c6d5939c57a91fb93ee81cbfac1c546ff5ab41eeb30ed076c41a45"
    "cdf1d6ccb0837073bc8874a05be7981036bfec231cc2b5ba4b9d7f8c8ae2da18ddab278a15eb"
    "b0d43a8b7700c7bbccfabaa46a175cf8515d8d16cda70e719798785a41b3f01f872d65cd2949"
    "d2872c91a95fcca9d8bb5318e7d6ec65a645f6cecf48f61e3dd2cfcb3acdbb922924167f8aa8"
    "5c0c457133"
)

COMMIT_1 = bytes.fromhex(
    "08f51e0dc5867851a90000ef4de29460898304b40e9010051c7fd733921fe77459"
)

VECTOR_2 = bytes.fromhex(
    "400300901a6164bb851a78351ee0d596710f188ef333f075fed6c6116b4289eaa20c89253781"
    "10f9f09bda682ad92e0c4517546d02d2215dbc10f88ff19240a9c724001bc8750ff68f938b78"
    "62733c864b617c0fc641c9b3c1307fd4ee9f37089b6423d5e61a0354749b0bae6f2b1ef54044"
    "aa12e8bde0a68589f1a9d03f2ec61f11f544699931102e64c644db47066dd5f28d190039b8ca"
    "da5c1d83bda36dbf97dd8386c956e2bb374b2db59df27a6a2547fa0305c5da73e196152123e5"
    "ef5536ddf1b13f331a916c7364d388e7c6c90429ae5527a08060af0c092fc81be6169eed29c7"
    "93cec70ddf1f28baf338c3aa99d92141b810a54837ec60da645a7355d7ff23faf6c6f4e2ca99"
    "2f303648738b57a66212a3e75ca8d1e6850559fe2b44e4731cc3563207654a58af2b3f36cab4"
    "1d5c2a461ff763594f2bd0f6fccf0409b7651b"
)

COMMIT_2 = bytes.fromhex(
    "0925a4bdc45769eb4f340feab8e472045406e5d6851542ea6e1d11119c56f81045"
)

VECTOR_3 = bytes.fromhex(
    "20ffffffffffffffffdc7d0b790eaf41a58e9b0c5ba3ee7dfd3d6bf3ac048a4375b0b70e92d7"
    "dff076c4a5b62ff1b5fbb4b629ea349b16300d06f1b43f0d735975bf5d1959ef11f0bf"
)

COMMIT_3 = bytes.fromhex(
    "08c7ea407d2638a299b9402278175765b336821842c557045e585ef6408b247310"
)

NONCE_3 = bytes.fromhex(
    "84509469a34b6c621ac7e20e079a6f855f2650cd885a9faa235e0ae07ec5e9f1"
)

BLIND_3 = bytes.fromhex(
    "6889478c77eccc2b6501786b068b3894c06b9b4c02a6c8f6c034ea3557f4e137"
)


def test_vector_1_verifies() -> None:
    """secp256k1-zkp's own first fixed vector: a proof with no message."""
    assert r.verify(COMMIT_1, VECTOR_1) == (86, 25586)


def test_vector_2_verifies() -> None:
    """secp256k1-zkp's own second fixed vector: a proof with a message."""
    assert r.verify(COMMIT_2, VECTOR_2) == (0, 15)


def test_vector_3_round_trips() -> None:
    """secp256k1-zkp's own third fixed vector: a single-value proof."""
    assert r.verify(COMMIT_3, VECTOR_3) == (2**64 - 1, 2**64 - 1)

    blind, value, message, min_value, max_value = r.rewind(COMMIT_3, VECTOR_3, NONCE_3)
    assert blind == BLIND_3
    assert value == 2**64 - 1
    assert (min_value, max_value) == (2**64 - 1, 2**64 - 1)
    assert message == b""


@pytest.mark.parametrize("min_value", [0, 7])
@pytest.mark.parametrize("exp", [-1, 0, 4])
def test_sign_verify_rewind_round_trips(exp: int, min_value: int) -> None:
    """`ISS 608`'s own "both exponents, with and without min_value"."""
    blind = secrets.token_bytes(32)
    nonce = secrets.token_bytes(32)
    value = min_value + 1000

    commit = g.pedersen_commit(blind, value)
    proof = r.sign(commit, blind, nonce, value, min_value=min_value, exp=exp)

    verified = r.verify(commit, proof)
    assert verified is not None
    proof_min, proof_max = verified
    assert proof_min <= value <= proof_max
    if exp == -1:
        # "-1 is a special case that makes the value public", the
        # header's own words: the range collapses to the value itself
        assert (proof_min, proof_max) == (value, value)

    rewound_blind, rewound_value, _message, rewound_min, rewound_max = r.rewind(
        commit, proof, nonce
    )
    assert rewound_blind == blind
    assert rewound_value == value
    assert (rewound_min, rewound_max) == (proof_min, proof_max)


def test_sign_embeds_a_message_rewind_recovers() -> None:
    """A message `sign` embeds is what `rewind` recovers, zero-padded."""
    blind = secrets.token_bytes(32)
    nonce = secrets.token_bytes(32)
    message = b"btclib-secp256k1 " + secrets.token_bytes(16)

    commit = g.pedersen_commit(blind, 100)
    proof = r.sign(commit, blind, nonce, 100, message=message)

    _blind, _value, recovered, _min, _max = r.rewind(commit, proof, nonce)
    assert recovered[: len(message)] == message
    assert set(recovered[len(message) :]) <= {0}


def test_verify_rejects_a_proof_for_a_different_commitment() -> None:
    """A real proof does not verify against a commitment it was not made for."""
    blind = secrets.token_bytes(32)
    nonce = secrets.token_bytes(32)
    commit = g.pedersen_commit(blind, 5)
    proof = r.sign(commit, blind, nonce, 5)

    other_commit = g.pedersen_commit(secrets.token_bytes(32), 6)
    assert r.verify(other_commit, proof) is None


def test_rewind_rejects_the_wrong_nonce() -> None:
    """A real proof does not rewind under a nonce it was not signed with."""
    blind = secrets.token_bytes(32)
    commit = g.pedersen_commit(blind, 5)
    proof = r.sign(commit, blind, secrets.token_bytes(32), 5)

    with pytest.raises(ValueError, match="proof does not verify, or rewind failed"):
        r.rewind(commit, proof, secrets.token_bytes(32))


def test_info_matches_verify() -> None:
    """`info`'s own range agrees with `verify`'s, for a real proof."""
    blind = secrets.token_bytes(32)
    commit = g.pedersen_commit(blind, 500)
    proof = r.sign(commit, blind, secrets.token_bytes(32), 500)

    exp, _mantissa, min_value, max_value = r.info(proof)
    assert exp == 0
    assert r.verify(commit, proof) == (min_value, max_value)


def test_max_size_bounds_a_real_proof() -> None:
    """`max_size`'s own bound holds for a proof the library actually made."""
    blind = secrets.token_bytes(32)
    commit = g.pedersen_commit(blind, 12345)
    proof = r.sign(commit, blind, secrets.token_bytes(32), 12345)
    assert len(proof) <= r.max_size(2**64 - 1, 0)


# captured from test_borromean_verify_api_internal, two rings of 4 and 2
# members -- the module docstring above has how, and the triple
# verification it was put through before landing here
BORROMEAN_RSIZES = [4, 2]
BORROMEAN_E0 = bytes.fromhex(
    "b290c94c649f2ba65776a1fdb66a13f380b6b20befbf4c3e6bd3533b30b376ad"
)
BORROMEAN_S = bytes.fromhex(
    "185ab3b091b9dda5b12cdcca92457f268f2edcf2d2bfbbbe13fe4853f9b22ad"
    "6d712dbea3448379f539c9ae555cb623acfb9433ecd6c09482db20aa96d5e34"
    "ded9470ea4d0e27e1a172884e70dce8922684c14266ababd558daec77807e6d"
    "b824bffa9daac39ee3a05b255eb7d196156436952d268ec00db6fd3fb58cf1e"
    "0c4b602bd8a0f0a9b9a95453ba1a5dae8c10fda95ab43b9a460990bb71e0444"
    "b6a693217cf9ffa903732576a586c504bd955f9a2bb476a6083c457189bb5f8"
    "d22b56"
)
BORROMEAN_M = bytes.fromhex(
    "00000000ffffffffffffffff0f000000001ffc030080ff0180ff010000000000"
)
BORROMEAN_PUBKEYS = [
    bytes.fromhex("0363340d8318905ff6a917ee5520e9e4ead2291734f727cac38acd62550db57c76"),
    bytes.fromhex("0300000000f0ffff1f0000f0ff7f0000000000000000000000000f0000ffff0000"),
    bytes.fromhex("0200ffffff03000000e0ffffff0f0000e0ffffffc7ffffffffffffff0000000000"),
    bytes.fromhex("027c0080ff71c0e3ffffffff0100f08fffffff1f00007f000000000000fe000000"),
    bytes.fromhex("0200000000e003000000000000f03f0000f0ffff00000000e0ffff0300feffff7f"),
    bytes.fromhex("0396f8e01c7636b0f53674e7edb0897e58eed50ae698f15945e398f8585527fd5f"),
]


def test_borromean_verify_accepts_the_captured_vector() -> None:
    """The captured tuple verifies against the real library."""
    assert (
        r.borromean_verify(
            BORROMEAN_E0,
            BORROMEAN_S,
            BORROMEAN_M,
            BORROMEAN_PUBKEYS,
            BORROMEAN_RSIZES,
        )
        is True
    )


def test_borromean_verify_rejects_a_tampered_signature() -> None:
    """Flipping one byte of `s` is a verification failure, not an exception."""
    tampered = bytearray(BORROMEAN_S)
    tampered[0] ^= 0xFF
    assert (
        r.borromean_verify(
            BORROMEAN_E0,
            bytes(tampered),
            BORROMEAN_M,
            BORROMEAN_PUBKEYS,
            BORROMEAN_RSIZES,
        )
        is False
    )


@pytest.mark.parametrize("value", [0, 1000, 2**63, 2**64 - 1])
def test_max_size_bounds_the_proof_of_the_value_it_is_asked_for(value: int) -> None:
    """`max_size(value, 0)` takes every value `sign` does, 0 included.

    "The largest value that might be passed as `value` to `sign`", as its
    docstring has it, so the proof of that very value is what it bounds:
    the two ends of `[0, 2**64)` and 2**63 between them are all
    accepted, and none of them makes a proof larger than the bound.
    """
    commit = g.pedersen_commit(BLIND_3, value)
    proof = r.sign(commit, BLIND_3, NONCE_3, value)
    assert len(proof) <= r.max_size(value, 0)


def test_sign_reproduces_the_third_fixed_vector() -> None:
    """Signing what `VECTOR_3` proves, under its own blind and nonce, is it.

    `2**64 - 1` is both the value and the range's only member, which
    `exp=-1` says outright; signing is deterministic in the blind and
    the nonce, so the octets are the ones secp256k1-zkp's own test
    carries. The value and the `min_value` are the last a `uint64_t`
    holds, and both go through unchanged.
    """
    proof = r.sign(COMMIT_3, BLIND_3, NONCE_3, 2**64 - 1, min_value=2**64 - 1, exp=-1)
    assert proof == VECTOR_3


def test_sign_proves_a_value_of_the_full_width() -> None:
    """A proof of `2**64 - 1` over the widest range there is, and its rewind.

    `min_bits` at its default and `min_value` at 0 make the range `[0,
    2**64)`, whose proof is larger than `max_size` answers for a value
    below 2**63: the buffer `sign` hands the library is sized for the
    widest proof, and holds this one only if it is.
    """
    commit = g.pedersen_commit(BLIND_3, 2**64 - 1)
    proof = r.sign(commit, BLIND_3, NONCE_3, 2**64 - 1)

    assert r.verify(commit, proof) == (0, 2**64 - 1)
    blind, value, _message, _min, _max = r.rewind(commit, proof, NONCE_3)
    assert (blind, value) == (BLIND_3, 2**64 - 1)


def test_sign_states_a_range_from_zero_by_default() -> None:
    """With no `min_value` the proven range starts at 0, for 0 as for any value.

    A default of 1 would have the library refuse the value 0, whose
    proof is `[0, 1]`, and state a range from 1 for any other.
    """
    zero = g.pedersen_commit(BLIND_3, 0)
    assert r.verify(zero, r.sign(zero, BLIND_3, NONCE_3, 0)) == (0, 1)

    commit = g.pedersen_commit(BLIND_3, 100)
    verified = r.verify(commit, r.sign(commit, BLIND_3, NONCE_3, 100))
    assert verified is not None
    assert verified[0] == 0


def test_extra_commit_is_covered_by_the_proof_and_asked_for_back() -> None:
    """A proof signed over `extra_commit` verifies and rewinds only over it.

    `extra_commit` is bytes the proof's signature covers: `verify` and
    `rewind` take the same bytes, and neither answers for a proof
    whose bytes are not the ones it was given.
    """
    commit = g.pedersen_commit(BLIND_3, 100)
    proof = r.sign(commit, BLIND_3, NONCE_3, 100, extra_commit=b"context")

    assert r.verify(commit, proof, extra_commit=b"context") == (0, 127)
    assert r.verify(commit, proof, extra_commit=b"another") is None
    assert r.verify(commit, proof) is None
    _blind, value, _message, _min, _max = r.rewind(
        commit, proof, NONCE_3, extra_commit=b"context"
    )
    assert value == 100
    with pytest.raises(ValueError, match="rewind failed"):
        r.rewind(commit, proof, NONCE_3, extra_commit=b"another")

    assert r.verify(commit, r.sign(commit, BLIND_3, NONCE_3, 100)) == (0, 127)


def test_sign_embeds_a_message_of_the_largest_length() -> None:
    """3968 octets go into a proof of the full mantissa, and come out whole.

    The room for a message depends on the proof's shape, so it is a
    proof over 64 bits, `min_bits=64`, that carries all of what
    `MAX_MESSAGE_LEN` allows, and `rewind` has a buffer as large as that.
    One octet more is refused before the library is asked.
    """
    commit = g.pedersen_commit(BLIND_3, 100)
    message = bytes(range(256)) * 15 + bytes(128)
    assert len(message) == 3968

    proof = r.sign(commit, BLIND_3, NONCE_3, 100, min_bits=64, message=message)
    _blind, _value, recovered, _min, _max = r.rewind(commit, proof, NONCE_3)
    assert recovered == message

    with pytest.raises(ValueError, match="message must be at most 3968 bytes"):
        r.sign(commit, BLIND_3, NONCE_3, 100, min_bits=64, message=message + b"\x00")


def test_borromean_verify_answers_for_the_largest_shape_the_header_allows() -> None:
    """128 keys in 32 rings reach the library: a verdict, not a refusal."""
    assert (
        r.borromean_verify(
            BORROMEAN_E0,
            bytes(32) * 128,
            BORROMEAN_M,
            [BORROMEAN_PUBKEYS[0]] * 128,
            [4] * 32,
        )
        is False
    )
