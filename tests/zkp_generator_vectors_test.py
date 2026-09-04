# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""`zkp.generator` against the real library and its own fixed vectors.

Every test here is marked `zkp`: it needs `BTCLIB_LIBSECP256K1_ZKP=true`,
which is what makes `import btclib_secp256k1.zkp.generator` reach for a
real generator and a real Pedersen commitment rather than the pure-python
stand-in `tests/zkp_generator_test.py` drives the same module's own
control flow with.

`test_generator_fixed_vector` and `test_pedersen_commitment_fixed_vector`
lift secp256k1-zkp's own vectors from
`secp256k1-zkp/src/modules/generator/tests_impl.h`
(`test_generator_fixed_vector`, `test_pedersen_commitment_fixed_vector`):
`2*G`'s serialization, parsed both as a generator and as a commitment,
each with the malleated-marker-byte cases the C test also carries.

`test_h_is_pinned_against_btclib` is `ISS 608
<https://github.com/btclib-org/btclib-secp256k1/issues/608>`_'s own
measurement made an assertion: btclib-org/btclib#1055 already pins
`pedersen.second_generator(secp256k1, sha256)`'s x-coordinate to this
same value, independently of this library -- `generator.h()` is what
lets that pin be checked against the library instead of against a copy
of the bytes, and this is the other half of the same check, run here.
"""

from __future__ import annotations

import secrets

import pytest

pytest.importorskip("_btclib_secp256k1_zkp")

from btclib_secp256k1.zkp import generator as g

pytestmark = pytest.mark.zkp

TWO_G = bytes.fromhex(
    "0bc6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5"
)
COMMIT_TWO_G = bytes.fromhex(
    "09c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5"
)


def test_generator_fixed_vector() -> None:
    """secp256k1-zkp's own vector, `2*G`, and its malleations."""
    parsed = g.parse(TWO_G)
    assert g.serialize(parsed) == TWO_G

    # the malleated cases secp256k1-zkp's own test_generator_fixed_vector
    # carries: only the marker byte (0x0a or 0x0b) differs from a valid
    # generator, and only one of the two malleations parses
    malleated = bytearray(g.serialize(parsed))
    malleated[0] = 0x0A
    g.parse(bytes(malleated))
    malleated[0] = 0x08
    with pytest.raises(ValueError, match="invalid generator"):
        g.parse(bytes(malleated))


def test_pedersen_commitment_fixed_vector() -> None:
    """secp256k1-zkp's own vector, `2*G`'s commitment, and its malleations."""
    parsed = g.pedersen_commitment_parse(COMMIT_TWO_G)
    assert g.pedersen_commitment_serialize(parsed) == COMMIT_TWO_G

    malleated = bytearray(g.pedersen_commitment_serialize(parsed))
    malleated[0] = 0x08
    g.pedersen_commitment_parse(bytes(malleated))
    malleated[0] = 0x0C
    with pytest.raises(ValueError, match="invalid Pedersen commitment"):
        g.pedersen_commitment_parse(bytes(malleated))


def test_h_is_pinned_against_btclib() -> None:
    """`h()` matches btclib's own independent pin of the same point.

    btclib-org/btclib#1055's own pin, tests/ecc/pedersen_test.py's
    test_second_generator, for the (secp256k1, sha256) pair: the x
    coordinate of pedersen.second_generator(secp256k1, sha256). The
    generator serialization's marker byte is this library's own format,
    not part of that pin.
    """
    x_h = 0x50929B74C1A04954B78B4B6035E97A5E078A5A0F28EC96D547BFEE9ACE803AC0
    assert g.h()[1:] == x_h.to_bytes(32, "big")


def test_generate_is_deterministic_in_the_seed() -> None:
    """The same seed always generates the same generator."""
    seed = secrets.token_bytes(32)
    assert g.generate(seed) == g.generate(seed)
    assert g.generate(seed) != g.generate(secrets.token_bytes(32))


def test_generate_blinded_differs_from_generate() -> None:
    """A nonzero blind changes the generator `generate` would answer."""
    seed = secrets.token_bytes(32)
    blind = secrets.token_bytes(32)
    assert g.generate_blinded(seed, blind) != g.generate(seed)


@pytest.mark.parametrize("blind", [1, 2**255, secrets.token_bytes(32)])
@pytest.mark.parametrize("value", [0, 42, 2**64 - 1])
def test_pedersen_commit_round_trips_through_octets(
    blind: bytes | int, value: int
) -> None:
    """A commitment round-trips, `blind` given as an int or as bytes."""
    commit = g.pedersen_commit(blind, value)
    assert (
        g.pedersen_commitment_serialize(g.pedersen_commitment_parse(commit)) == commit
    )


def test_pedersen_verify_tally_of_the_same_commitment() -> None:
    """A commitment tallies against itself."""
    commit = g.pedersen_commit(secrets.token_bytes(32), 100)
    assert g.pedersen_verify_tally([commit], [commit]) is True


def test_pedersen_blind_sum_matches_the_commitments_it_backs() -> None:
    """A blind `pedersen_blind_sum` corrects is what makes two sides tally.

    A set of Pedersen commitments to the same total value on each side
    sums to zero exactly when their blinding factors do, which is
    pedersen_blind_sum's own contract restated as a check: build two
    commitments to 30 and to 12 + 18, with a blinding factor
    pedersen_blind_sum makes cancel, and pedersen_verify_tally is what
    the equality is measured through.
    """
    blind_in = secrets.token_bytes(32)
    blind_out_1 = secrets.token_bytes(32)
    blind_out_2 = g.pedersen_blind_sum([blind_in, blind_out_1], 1)

    commit_in = g.pedersen_commit(blind_in, 30)
    commit_out_1 = g.pedersen_commit(blind_out_1, 12)
    commit_out_2 = g.pedersen_commit(blind_out_2, 18)

    assert g.pedersen_verify_tally([commit_in], [commit_out_1, commit_out_2]) is True


def test_pedersen_blind_generator_blind_sum_makes_blinded_commitments_tally() -> None:
    """Commitments under different blinded generators tally, once corrected.

    The header's own worked example: A' = A + r*G is a blinded
    generator, and a commitment v*A' + r'*G really has the form
    v*A + (v*r + r')*G. pedersen_blind_generator_blind_sum corrects the
    last blinding factor so that sum(v*r + r') is zero across every
    commitment, which is exactly what makes pedersen_verify_tally pass
    for commitments made under *different* blinded generators -- a
    case an unblinded pedersen_verify_tally (one shared gen) cannot
    exercise at all.
    """
    seed = secrets.token_bytes(32)
    gen_a = g.generate(seed)
    gen_blind_1 = secrets.token_bytes(32)
    gen_blind_2 = secrets.token_bytes(32)
    gen_1 = g.generate_blinded(seed, gen_blind_1)
    gen_2 = g.generate_blinded(seed, gen_blind_2)

    # every commitment is of the same underlying asset, gen_a -- two of
    # them under a blinded form of it (gen_1 = gen_a + gen_blind_1*G, and
    # likewise for gen_2), the third under gen_a itself, i.e. blinded by
    # 0 -- or pedersen_verify_tally's own point equation would not
    # cancel however the blinding factors were corrected
    values = [30, 12, 18]
    generator_blinds = [gen_blind_1, gen_blind_2, bytes(32)]
    blind_in = secrets.token_bytes(32)
    blind_out_1 = secrets.token_bytes(32)
    blinding_factors = [blind_in, blind_out_1, bytes(32)]

    corrected = g.pedersen_blind_generator_blind_sum(
        values, generator_blinds, blinding_factors, 1
    )

    commit_in = g.pedersen_commit(blind_in, 30, gen_1)
    commit_out_1 = g.pedersen_commit(blind_out_1, 12, gen_2)
    commit_out_2 = g.pedersen_commit(corrected, 18, gen_a)

    assert g.pedersen_verify_tally([commit_in], [commit_out_1, commit_out_2]) is True
