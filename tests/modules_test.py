# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for the ecdh, recovery and ellswift libsecp256k1 modules.

Wherever possible the results are cross-checked against the other
bindings (dsa, ssa, keys) instead of against vendored constants: the
ECDH secret is recomputed from the shared point, and the recoverable
signature is compared with the deterministic ECDSA one.

`musig` has its own tests, in `tests/musig_test.py`: it is the one
module here that holds state across calls, which is a different shape
of test from the other three, one call each against an equation checked
another way.
"""

from __future__ import annotations

import array
import hashlib
from collections.abc import Iterator, Mapping
from typing import Any

import pytest
from typing_extensions import override

from btclib_secp256k1 import (
    _secret,
    dsa,
    ecdh,
    ellswift,
    ffi,
    keys,
    lib,
    recovery,
    silentpayments,
    ssa,
    xonly,
)

msg = hashlib.sha256(b"btclib_secp256k1").digest()

# secp256k1 group order
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


def compress(pubkey_bytes: bytes) -> bytes:
    """Compress an uncompressed 65-byte public key."""
    return bytes([2 + (pubkey_bytes[64] & 1)]) + pubkey_bytes[1:33]


def test_ecdh() -> None:
    """Both parties reach one secret, and it is the hash of the point.

    Cross-checked three ways rather than against a constant: the two
    parties agree, the secret is the SHA256 of the compressed shared
    point recomputed here, and `keys.pubkey_tweak_mul` gives that same
    point -- which is why the hash of the ecdh call is not a parameter, a
    protocol wanting another derivation applying it to the point.
    """
    prvkey_a, prvkey_b = 3, 5
    pubkey_a, pubkey_b = (
        keys.pubkey_from_prvkey(prvkey_a, compressed=False),
        keys.pubkey_from_prvkey(prvkey_b, compressed=False),
    )

    secret = ecdh.shared_secret(pubkey_b, prvkey_a)
    # both parties compute the same secret
    assert secret == ecdh.shared_secret(pubkey_a, prvkey_b)
    # which is the SHA256 of the compressed shared point
    shared_point = keys.pubkey_from_prvkey(prvkey_a * prvkey_b, compressed=False)
    assert secret == hashlib.sha256(compress(shared_point)).digest()
    # bytes and int private keys are interchangeable
    assert secret == ecdh.shared_secret(pubkey_b, prvkey_a.to_bytes(32, "big"))

    # the same point is what shared_point answers, which is why the hash
    # function of the ecdh call is not exposed: a protocol needing another
    # derivation applies it to this
    assert secret == hashlib.sha256(ecdh.shared_point(pubkey_b, prvkey_a)).digest()
    assert ecdh.shared_point(pubkey_b, prvkey_a, compressed=False) == shared_point
    assert ecdh.shared_point(pubkey_b, prvkey_a) == compress(shared_point)
    assert secret == hashlib.sha256(keys.pubkey_tweak_mul(pubkey_b, prvkey_a)).digest()


@pytest.mark.parametrize("bits", [256, 128, 64])
def test_ecdh_shared_point_is_the_point_tweak_mul_answers(bits: int) -> None:
    """The two multiplications agree, whatever the length of the scalar.

    `keys.pubkey_tweak_mul` is the variable-time one, and a short scalar
    is where it does less work, so the agreement is asserted on scalars
    of each length, their top bit set -- and at the two ends of the range,
    1 and n - 1.
    """
    pubkey_bytes = keys.pubkey_from_prvkey(0xC0FFEE)
    digest = int.from_bytes(hashlib.sha256(b"%d" % bits).digest(), "big")
    top_bit_set = (1 << (bits - 1)) | (digest >> (257 - bits))
    for scalar in (top_bit_set, 1, N - 1):
        for compressed in (True, False):
            point = ecdh.shared_point(pubkey_bytes, scalar, compressed)
            assert point == keys.pubkey_tweak_mul(pubkey_bytes, scalar, compressed)


def test_ecdh_invalid_inputs() -> None:
    """A zero key, a short key and an unparsable public key are refused.

    And the group order and a key too wide for 32 bytes, by
    `ecdh.shared_point` as by `ecdh.shared_secret`. `secp256k1_ecdh`
    reports zero and the order alike, as scalars it will not multiply by,
    and `keys.pubkey_tweak_mul` refuses the same two.
    """
    pubkey_bytes = keys.pubkey_from_prvkey(1, compressed=False)

    for call in (ecdh.shared_secret, ecdh.shared_point):
        with pytest.raises(ValueError, match="invalid private key"):
            call(pubkey_bytes, 0)
        with pytest.raises(ValueError, match="invalid private key"):
            call(pubkey_bytes, N)
        with pytest.raises(ValueError, match="32 bytes"):
            call(pubkey_bytes, b"\x01" * 31)
        with pytest.raises(ValueError, match="must fit in 32 bytes"):
            call(pubkey_bytes, 2**256)
        with pytest.raises(ValueError, match="public key"):
            call(b"\x02" + b"\x00" * 32, 1)
    for scalar in (0, N):
        with pytest.raises(ValueError, match="invalid tweak"):
            keys.pubkey_tweak_mul(pubkey_bytes, scalar)


def test_recovery() -> None:
    """A recoverable signature recovers the signer, and is the ECDSA one.

    The recovery id is 0 or 1 for a key of this curve, and the DER form
    of the recoverable signature equals what `dsa.sign` produces for the
    same message and key -- so the two entry points are one signature,
    not two. A nonce contribution gives a different signature that is
    still recoverable.
    """
    prvkey = 7
    pubkey_bytes = compress(keys.pubkey_from_prvkey(prvkey, compressed=False))

    signature_bytes, recid = recovery.sign(msg, prvkey)
    assert len(signature_bytes) == 64
    assert recid in (0, 1)
    assert recovery.recover(msg, signature_bytes, recid) == pubkey_bytes

    # the recoverable signature is the deterministic ECDSA one
    der_bytes = recovery.to_der(signature_bytes, recid)
    assert der_bytes == dsa.sign(msg, prvkey)
    assert dsa.verify(msg, pubkey_bytes, der_bytes)

    # a custom nonce yields a different, still recoverable signature
    custom = recovery.sign(msg, prvkey, b"\x01" * 32)
    assert custom[0] != signature_bytes
    assert recovery.recover(msg, *custom) == pubkey_bytes

    # the recovered key comes back in either form, this being
    # keys.serialize and the same point either way
    uncompressed = recovery.recover(msg, signature_bytes, recid, compressed=False)
    assert uncompressed == keys.pubkey_from_prvkey(prvkey, compressed=False)
    assert compress(uncompressed) == pubkey_bytes


def test_recovery_invalid_inputs() -> None:
    """Every argument the recovery module bounds is refused out of range.

    A zero private key, a message hash that is not 32 octets, a compact
    signature that is not 64, a recovery id outside 0..3, and a compact
    signature whose r cannot be parsed.
    """
    signature_bytes, recid = recovery.sign(msg, 7)

    with pytest.raises(ValueError, match="private key"):
        recovery.sign(msg, 0)
    with pytest.raises(ValueError, match="32 bytes"):
        recovery.sign(msg[1:], 7)
    with pytest.raises(ValueError, match="message hash"):
        recovery.recover(msg[1:], signature_bytes, recid)
    with pytest.raises(ValueError, match="64 bytes"):
        recovery.recover(msg, signature_bytes[1:], recid)
    with pytest.raises(ValueError, match="64 bytes"):
        recovery.to_der(signature_bytes[1:], recid)
    with pytest.raises(ValueError, match="recovery id"):
        recovery.recover(msg, signature_bytes, 4)
    with pytest.raises(ValueError, match="recovery id"):
        recovery.to_der(signature_bytes, -1)
    with pytest.raises(ValueError, match="compact signature"):
        # an out of range r (and s) cannot be parsed
        recovery.recover(msg, b"\xff" * 64, 0)
    with pytest.raises(ValueError, match="recovery failed"):
        # a zero r parses, but no point can be recovered from it
        recovery.recover(msg, b"\x00" * 64, 0)
    with pytest.raises(ValueError, match="aux_rand32 must be 32 bytes"):
        recovery.sign(msg, 7, b"\x01" * 33)


def test_ellswift() -> None:
    """An ElligatorSwift encoding decodes back, and the x-only ECDH agrees.

    The encoding is 64 octets and randomized, so a fresh one differs from
    the last; supplying the randomness makes it a function of that, which
    is what allows the assertion at all. The BIP324 secret is bound to the
    transcript rather than to the two keys: both parties reach one value
    naming their own side, and swapping the roles changes it.
    """
    prvkey_a, prvkey_b = 11, 13
    pubkey_a = compress(keys.pubkey_from_prvkey(prvkey_a, compressed=False))

    ell_a = ellswift.create(prvkey_a, b"\x01" * 32)
    assert len(ell_a) == 64
    # the encoding decodes back to the public key
    assert ellswift.decode(ell_a) == pubkey_a
    # as does the one of an already computed public key
    assert ellswift.decode(ellswift.encode(pubkey_a)) == pubkey_a
    # the randomness can be supplied, and then the encoding is a function
    # of it: 32 bytes, like every other entropy argument here
    fixed = ellswift.encode(pubkey_a, b"\x02" * 32)
    assert fixed == ellswift.encode(pubkey_a, b"\x02" * 32)
    assert ellswift.decode(fixed) == pubkey_a
    # the encoding is randomized: a fresh one differs
    assert ellswift.create(prvkey_a) != ell_a
    # and the decoding comes back in either form, this being
    # keys.serialize and the same point either way
    assert ellswift.decode(ell_a, compressed=False) == keys.pubkey_from_prvkey(
        prvkey_a, compressed=False
    )

    # x-only ECDH: both parties agree on the BIP324 shared secret
    ell_b = ellswift.create(prvkey_b)
    secret = ellswift.xdh(ell_a, ell_b, prvkey_a, 0)
    assert len(secret) == 32
    assert secret == ellswift.xdh(ell_a, ell_b, prvkey_b, 1)
    # the secret is bound to the transcript: swapping the roles changes it
    assert secret != ellswift.xdh(ell_b, ell_a, prvkey_b, 0)


def test_ellswift_invalid_inputs() -> None:
    """Every argument the ellswift module bounds is refused out of range.

    A zero private key, a key and an entropy argument that are not 32
    octets, a public key that does not parse, an encoding that is not 64
    octets, and a party that is neither 0 nor 1.
    """
    ell = ellswift.create(11)

    with pytest.raises(ValueError, match="private key"):
        ellswift.create(0)
    with pytest.raises(ValueError, match="32 bytes"):
        ellswift.create(b"\x01" * 31)
    with pytest.raises(ValueError, match="aux_rand32 must be 32 bytes"):
        ellswift.create(11, b"\x01" * 33)
    with pytest.raises(ValueError, match="public key"):
        ellswift.encode(b"\x02" + b"\x00" * 32)
    with pytest.raises(ValueError, match="aux_rand32 must be 32 bytes"):
        ellswift.encode(keys.pubkey_from_prvkey(11, compressed=False), b"\x01" * 31)
    with pytest.raises(ValueError, match="64 bytes"):
        ellswift.decode(ell[1:])
    with pytest.raises(ValueError, match="64 bytes"):
        ellswift.xdh(ell[1:], ell, 11, 0)
    with pytest.raises(ValueError, match="party"):
        ellswift.xdh(ell, ell, 11, 2)
    with pytest.raises(ValueError, match="private key"):
        ellswift.xdh(ell, ell, 0, 0)


def test_size_checks_refuse_both_sides() -> None:
    """Every size check of recovery and ellswift refuses both edges.

    The far edge of each, the one the tests above leave out: a check
    written `!= 32` or `!= 64` has two, and the first mutation session
    found every one of these surviving a `!=` turned into `<` or `>`.
    """
    prvkey = 7
    signature_bytes, recid = recovery.sign(msg, prvkey)
    ell = ellswift.create(prvkey)

    with pytest.raises(ValueError, match="message hash"):
        recovery.sign(msg + b"\x01", prvkey)
    with pytest.raises(ValueError, match="aux_rand32"):
        recovery.sign(msg, prvkey, b"\x01" * 31)
    with pytest.raises(ValueError, match="message hash"):
        recovery.recover(msg + b"\x01", signature_bytes, recid)
    with pytest.raises(ValueError, match="64 bytes"):
        recovery.recover(msg, signature_bytes + b"\x01", recid)
    with pytest.raises(ValueError, match="64 bytes"):
        recovery.to_der(signature_bytes + b"\x01", recid)

    with pytest.raises(ValueError, match="aux_rand32"):
        ellswift.create(prvkey, b"\x01" * 31)
    with pytest.raises(ValueError, match="aux_rand32"):
        ellswift.encode(keys.pubkey_from_prvkey(prvkey, compressed=False), b"\x01" * 33)
    with pytest.raises(ValueError, match="64 bytes"):
        ellswift.decode(ell + b"\x01")
    with pytest.raises(ValueError, match="64 bytes"):
        ellswift.xdh(ell + b"\x01", ell, prvkey, 0)
    with pytest.raises(ValueError, match="64 bytes"):
        ellswift.xdh(ell, ell + b"\x01", prvkey, 0)
    with pytest.raises(ValueError, match="64 bytes"):
        ellswift.xdh(ell, ell[:-1], prvkey, 0)


def test_every_recovery_id_of_the_curve_is_accepted() -> None:
    """A recovery id of 2 or 3 is a valid argument, not only 0 and 1.

    `recovery.sign` answers 0 or 1 for a key of this curve, so those are
    the only two the tests above ever pass, and a bound written
    `recid not in (0, 1, 2, 3)` was therefore asserted on one half of its
    own domain: the first mutation session found it surviving with 2 or 3
    dropped from that tuple. What the API accepts is the whole SEC 1 range,
    a recovery id being two bits, so `to_der` has to take all four --
    reached here through the parse alone, `recover` being free to fail on a
    candidate that names no key.
    """
    signature_bytes, _ = recovery.sign(msg, 7)

    for recid in (0, 1, 2, 3):
        assert len(recovery.to_der(signature_bytes, recid)) > 0

    # `recover` bounds the recovery id separately, so it needs its own
    # two: 2 and 3 name the candidate whose x is r + n, which exists only
    # when r + n < p -- some 2^-127 of secp256k1 signatures, so for this
    # one the recovery fails. What the assertion is about is *which* way it
    # fails: "public key recovery failed" says the id was accepted and the
    # arithmetic answered, where "the recovery id must be" would say the
    # bound had refused it
    for recid in (2, 3):
        with pytest.raises(ValueError, match="public key recovery failed"):
            recovery.recover(msg, signature_bytes, recid)


# The silent payment this section pays and scans back: an input funded by
# the private key 7, to an address of the scan key 13 and the spend key
# 17. The outpoint is 36 zero bytes -- a serialization like any other
# here, BIP352 reading it as bytes and never as a transaction reference
SP_INPUT_PRVKEY = (7).to_bytes(32, "big")
SP_SCAN_PRVKEY = (13).to_bytes(32, "big")
SP_SPEND_PRVKEY = (17).to_bytes(32, "big")
SP_INPUT_PUBKEY = keys.pubkey_from_prvkey(SP_INPUT_PRVKEY)
SP_SCAN_PUBKEY = keys.pubkey_from_prvkey(SP_SCAN_PRVKEY)
SP_SPEND_PUBKEY = keys.pubkey_from_prvkey(SP_SPEND_PRVKEY)
SP_OUTPOINT = bytes(36)


def sp_summary() -> bytes:
    """Summarize the one-input transaction this section's payment funds."""
    return silentpayments.prevouts_summary(SP_OUTPOINT, pubkeys_bytes=[SP_INPUT_PUBKEY])


def test_a_silent_payment_is_found_by_the_key_it_was_paid_to() -> None:
    """Pay an address, scan the transaction, and spend what was found.

    The BIP352 vectors are what pin the values; this pins the round trip
    the three functions make together, and the one thing the vectors
    cannot say -- that the tweak returned is the tweak that spends the
    output. Adding it to the spend private key has to give the private
    key of the taproot output found, which is checked by signing with it.
    """
    outputs = silentpayments.create_outputs(
        [(SP_SCAN_PUBKEY, SP_SPEND_PUBKEY)],
        SP_OUTPOINT,
        prvkeys=[SP_INPUT_PRVKEY],
    )
    found = silentpayments.scan_outputs(
        outputs, SP_SCAN_PRVKEY, sp_summary(), SP_SPEND_PUBKEY
    )

    assert [pubkey for pubkey, _, _ in found] == outputs
    for pubkey, tweak, label in found:
        assert label is None
        output_prvkey = keys.prvkey_tweak_add(SP_SPEND_PRVKEY, tweak)
        # the output is x-only, so what has to match is the x of the
        # tweaked key: signing with it is BIP340's own answer to that
        assert ssa.verify(msg, pubkey, ssa.sign(msg, output_prvkey))


def test_a_labeled_silent_payment_is_found_only_with_its_label() -> None:
    """A labeled output is invisible to a scan whose cache lacks the label.

    Both halves are the point. The label reaching the scan is what makes
    the output findable, and the same scan without it finding nothing is
    what says the label was doing the work -- an unlabeled address would
    have matched anyway.
    """
    label, label_tweak = silentpayments.label(SP_SCAN_PRVKEY, 1)
    labeled_spend_pubkey = silentpayments.labeled_spend_pubkey(SP_SPEND_PUBKEY, label)
    outputs = silentpayments.create_outputs(
        [(SP_SCAN_PUBKEY, labeled_spend_pubkey)],
        SP_OUTPOINT,
        prvkeys=[SP_INPUT_PRVKEY],
    )

    found = silentpayments.scan_outputs(
        outputs,
        SP_SCAN_PRVKEY,
        sp_summary(),
        SP_SPEND_PUBKEY,
        labels={label: label_tweak},
    )
    assert [(pubkey, found_label) for pubkey, _, found_label in found] == [
        (outputs[0], label)
    ]

    # the tweak reported is the whole of what spends the output, the label
    # tweak included: one addition to the spend private key, not two. What
    # says the label is in there is the unlabeled payment to the same scan
    # key, whose tweak is this one less the label's -- both being the same
    # shared secret at the same k
    pubkey, tweak, _ = found[0]
    assert ssa.verify(
        msg, pubkey, ssa.sign(msg, keys.prvkey_tweak_add(SP_SPEND_PRVKEY, tweak))
    )
    unlabeled = silentpayments.create_outputs(
        [(SP_SCAN_PUBKEY, SP_SPEND_PUBKEY)], SP_OUTPOINT, prvkeys=[SP_INPUT_PRVKEY]
    )
    unlabeled_tweak = silentpayments.scan_outputs(
        unlabeled, SP_SCAN_PRVKEY, sp_summary(), SP_SPEND_PUBKEY
    )[0][1]
    assert keys.prvkey_tweak_add(unlabeled_tweak, label_tweak) == tweak

    assert (
        silentpayments.scan_outputs(
            outputs, SP_SCAN_PRVKEY, sp_summary(), SP_SPEND_PUBKEY
        )
        == []
    )
    # an empty cache is not the absence of one: it reaches libsecp256k1 as
    # a lookup function that never matches rather than as no function, and
    # has to answer the same
    assert (
        silentpayments.scan_outputs(
            outputs, SP_SCAN_PRVKEY, sp_summary(), SP_SPEND_PUBKEY, labels={}
        )
        == []
    )


def test_the_outputs_follow_the_recipient_order() -> None:
    """The n-th output is the n-th recipient's, whatever the order given.

    What the BIP352 vectors pin is the set of outputs, the assignment of
    a k within a group of recipients sharing a scan key not being
    determined by them. This is the other half: libsecp256k1 documents
    the outputs as ordered by the index of the recipient they belong to,
    and it reorders the array it is handed rather than the objects in it,
    so a wrong index would show up as an answer permuted with the input.

    The two recipients have *different* scan keys, which is what makes
    the assertion about the ordering alone: sharing one would put them in
    a group whose k assignment is libsecp256k1's, so reversing the list
    would change the output values as well as their places -- which is
    what this test asserted first, and what it fails on.
    """
    recipients = [
        (SP_SCAN_PUBKEY, SP_SPEND_PUBKEY),
        (keys.pubkey_from_prvkey(19), keys.pubkey_from_prvkey(23)),
    ]
    outputs = silentpayments.create_outputs(
        recipients, SP_OUTPOINT, prvkeys=[SP_INPUT_PRVKEY]
    )
    reversed_outputs = silentpayments.create_outputs(
        recipients[::-1], SP_OUTPOINT, prvkeys=[SP_INPUT_PRVKEY]
    )

    assert len(set(outputs)) == 2, "the two recipients share an output"
    assert reversed_outputs == outputs[::-1]


def test_a_taproot_input_pays_as_its_even_y_key() -> None:
    """The two sides agree on a taproot input, which is where parity is dropped.

    A taproot input contributes the even-y point of its x-only key, so
    the sender passes the private key as a taproot one and the recipient
    the 32 bytes: `taproot_prvkeys` negating where the y is odd is what
    makes the two the same point, and the private key here is chosen to
    be one that needs it.
    """
    # 6, not 3: the negation is only exercised by a key whose y is odd
    prvkey = (6).to_bytes(32, "big")
    xonly_pubkey, parity = xonly.from_pubkey(keys.pubkey_from_prvkey(prvkey))
    assert parity == 1, "this key no longer exercises the negation"

    outputs = silentpayments.create_outputs(
        [(SP_SCAN_PUBKEY, SP_SPEND_PUBKEY)], SP_OUTPOINT, taproot_prvkeys=[prvkey]
    )
    summary = silentpayments.prevouts_summary(
        SP_OUTPOINT, taproot_pubkeys_bytes=[xonly_pubkey]
    )
    found = silentpayments.scan_outputs(
        outputs, SP_SCAN_PRVKEY, summary, SP_SPEND_PUBKEY
    )

    assert [pubkey for pubkey, _, _ in found] == outputs


def test_the_prevouts_summary_carries_no_secret() -> None:
    """The summary is public data, and the same for every scan key.

    It holds the sum of the input public keys and the hash of the
    outpoint, so two recipients scanning one transaction build the same
    one -- which is why it is a separate function rather than an argument
    of the scan. The one input key makes the sum that key, so the
    expected octets are the outpoint and the key the test chose, neither
    of which came out of the function under test.
    """
    assert sp_summary() == sp_summary()
    assert len(sp_summary()) == silentpayments.SUMMARY_SIZE
    assert sp_summary() == SP_OUTPOINT + SP_INPUT_PUBKEY


def test_a_label_is_a_point_and_round_trips_through_its_33_bytes() -> None:
    """The 33 bytes of a label parse back into the label they came from.

    `labeled_spend_pubkey` and `parse_label` are what take one, and the
    parse is exercised through both: the same 33 bytes have to give the
    same labeled key, and a label is a point rather than an opaque blob
    -- the sum below is what says so.
    """
    label, _ = silentpayments.label(SP_SCAN_PRVKEY, 0)
    assert len(label) == silentpayments.LABEL_SIZE

    labeled = silentpayments.labeled_spend_pubkey(SP_SPEND_PUBKEY, label)
    assert labeled == keys.pubkey_combine([SP_SPEND_PUBKEY, label])
    assert silentpayments.labeled_spend_pubkey(
        SP_SPEND_PUBKEY, label, compressed=False
    ) == keys.pubkey_combine([SP_SPEND_PUBKEY, label], compressed=False)

    # and the 33 bytes parse back into the label the recipient made,
    # which is what lets a cache of them be used without going round
    # through the serialization at every address
    assert (
        keys.serialize(
            silentpayments._labeled_spend_pubkey_(
                keys.parse(SP_SPEND_PUBKEY), silentpayments.parse_label(label)
            )
        )
        == labeled
    )


def test_a_label_of_a_scan_key_is_the_scan_key_and_m() -> None:
    """A different m, or a different scan key, is a different label."""
    label, tweak = silentpayments.label(SP_SCAN_PRVKEY, 0)

    assert silentpayments.label(SP_SCAN_PRVKEY, 0) == (label, tweak)
    assert silentpayments.label(SP_SCAN_PRVKEY, 1) != (label, tweak)
    assert silentpayments.label(SP_SPEND_PRVKEY, 0) != (label, tweak)
    # the tweak is the label's own private key, m = 2**32 - 1 included
    assert keys.pubkey_from_prvkey(tweak) == label
    biggest, biggest_tweak = silentpayments.label(SP_SCAN_PRVKEY, 2**32 - 1)
    assert keys.pubkey_from_prvkey(biggest_tweak) == biggest


def test_silent_payment_creation_refuses_an_empty_recipient_list() -> None:
    """No recipient is nothing to pay, which is refused before the call."""
    with pytest.raises(ValueError, match="at least one recipient"):
        silentpayments.create_outputs([], SP_OUTPOINT, prvkeys=[SP_INPUT_PRVKEY])


def test_silent_payment_creation_refuses_a_transaction_with_no_keys() -> None:
    """No private key is no shared secret, and the two lists are both empty."""
    with pytest.raises(ValueError, match="at least one private key"):
        silentpayments.create_outputs([(SP_SCAN_PUBKEY, SP_SPEND_PUBKEY)], SP_OUTPOINT)


def test_silent_payment_creation_refuses_an_invalid_private_key() -> None:
    """A taproot private key libsecp256k1 rejects is named as one."""
    with pytest.raises(ValueError, match="invalid private key"):
        silentpayments.create_outputs(
            [(SP_SCAN_PUBKEY, SP_SPEND_PUBKEY)], SP_OUTPOINT, taproot_prvkeys=[0]
        )


@pytest.mark.parametrize(
    "recipient, message",
    [
        ((b"\x02" + bytes(32), SP_SPEND_PUBKEY), "invalid scan public key"),
        ((SP_SCAN_PUBKEY, b"\x02" + bytes(32)), "invalid spend public key"),
    ],
)
def test_silent_payment_creation_names_which_key_it_refused(
    recipient: tuple[bytes, bytes], message: str
) -> None:
    """Scan and spend are two arguments, and the exception says which.

    `keys.parse` would answer both with "invalid public key", which for a
    recipient built out of two keys is the half of the answer that does
    not help.

    Args:
        recipient: the pair to pay, one half of it unparsable.
        message: what the exception has to name.
    """
    with pytest.raises(ValueError, match=message):
        silentpayments.create_outputs(
            [recipient], SP_OUTPOINT, prvkeys=[SP_INPUT_PRVKEY]
        )


def test_a_label_m_outside_four_bytes_is_refused() -> None:
    """Refuse an m outside the uint32 the label index is.

    Left to cffi the answer is `OverflowError`, which is neither how this
    package reports an argument out of domain nor a message naming the
    argument.

    `2**32 + 1` is here because the two ends of the bound are not enough,
    which a mutation session said: with `<` mutated to `!=` the check
    reads `0 <= m != 2**32`, and both ends still raise -- `-1` fails the
    first comparison and `2**32` fails the second. A value *above* the
    bound is the one input that tells the two apart, so it is the one
    that kills that mutant.
    """
    for m in (-1, 2**32, 2**32 + 1):
        with pytest.raises(
            ValueError, match=r"the label m must be in \[0, 4294967295\]"
        ):
            silentpayments.label(SP_SCAN_PRVKEY, m)


def test_a_label_of_an_invalid_scan_key_is_refused() -> None:
    """A scan key outside [1, n-1] has no label, and libsecp256k1 says so."""
    with pytest.raises(ValueError, match="invalid scan private key"):
        silentpayments.label(0, 0)


def test_a_labeled_spend_pubkey_summing_to_infinity_is_refused() -> None:
    """The point at infinity has no serialization, and is reachable here.

    Only from a label that is not one BIP352 made: a label is a point,
    and the negation of the spend public key parses as one, so a caller
    holding both can ask for the sum that does not exist. The label
    `label` returns cannot do it -- it is a hash away from the key.
    """
    negated = keys.pubkey_negate(SP_SPEND_PUBKEY)

    with pytest.raises(ValueError, match="invalid labeled spend public key"):
        silentpayments.labeled_spend_pubkey(SP_SPEND_PUBKEY, negated)


def test_an_unparsable_label_is_refused() -> None:
    """33 bytes that are not a point are not a label."""
    with pytest.raises(ValueError, match="invalid label"):
        silentpayments.labeled_spend_pubkey(SP_SPEND_PUBKEY, b"\x02" + bytes(32))


def test_a_prevouts_summary_of_no_input_is_refused() -> None:
    """No input public key is no sum, and both lists are empty."""
    with pytest.raises(ValueError, match="at least one public key"):
        silentpayments.prevouts_summary(SP_OUTPOINT)


def test_a_prevouts_summary_checks_its_keys_before_its_outpoint() -> None:
    """Without a key, a short outpoint is not what is reported."""
    with pytest.raises(ValueError, match="at least one public key"):
        silentpayments.prevouts_summary(bytes(35))


def test_a_prevouts_summary_of_an_unparsable_taproot_key_is_refused() -> None:
    """An x that is not on the curve is not a taproot input key."""
    with pytest.raises(ValueError, match="invalid taproot public key"):
        silentpayments.prevouts_summary(SP_OUTPOINT, taproot_pubkeys_bytes=[bytes(32)])


def test_scanning_refuses_an_empty_output_list() -> None:
    """A transaction with no taproot output pays no silent payment.

    libsecp256k1 requires at least one -- `n_tx_outputs > 0` is an
    ARG_CHECK of its own -- and what a violated precondition gets a
    caller is a bare zero return, which this wrapper can only report as
    the scan having failed. So it is refused here instead, by the
    argument's own name.
    """
    with pytest.raises(ValueError, match="at least one transaction output"):
        silentpayments.scan_outputs([], SP_SCAN_PRVKEY, sp_summary(), SP_SPEND_PUBKEY)


def test_scanning_refuses_an_unparsable_output() -> None:
    """An output that is not an x-only public key is named as one."""
    with pytest.raises(ValueError, match="invalid transaction output"):
        silentpayments.scan_outputs(
            [bytes(32)], SP_SCAN_PRVKEY, sp_summary(), SP_SPEND_PUBKEY
        )


# a point of order 199 on y**2 = x**3 + 4, which is no point of secp256k1:
# x**3 + 7 is not a square modulo the field order, so no y completes this x
# on the curve. test_the_twist_x_has_no_y_on_the_curve checks that
TWIST_X = bytes.fromhex(
    "87282779b69dde36393a9a337766ca13a0d9f43aba42ceef40da64895a4f8dd6"  # pragma: allowlist secret
)


def test_the_twist_x_has_no_y_on_the_curve() -> None:
    """`TWIST_X` is refused as a public key for a reason checked here.

    Euler's criterion on x**3 + 7, in plain integers: the independent
    side of the refusals below.
    """
    p = 2**256 - 2**32 - 977
    x = int.from_bytes(TWIST_X, "big")
    assert pow(x**3 + 7, (p - 1) // 2, p) == p - 1


@pytest.mark.parametrize("size", [0, 68, 70, 101])
def test_scanning_refuses_a_summary_of_the_wrong_length(size: int) -> None:
    """A summary is `SUMMARY_SIZE` octets, whatever the length of another form.

    101 is the length of the raw struct earlier versions returned: it is
    refused, not read.

    Args:
        size: the length of the summary handed in.
    """
    summary = (sp_summary() * 2)[:size]
    with pytest.raises(ValueError, match="prevouts summary must be"):
        silentpayments.scan_outputs(
            [SP_INPUT_PUBKEY[1:]], SP_SCAN_PRVKEY, summary, SP_SPEND_PUBKEY
        )


@pytest.mark.parametrize("prefix", [2, 3])
@pytest.mark.parametrize(
    "x",
    [
        TWIST_X,
        (2**256 - 2**32 - 977).to_bytes(32, "big"),
        (2**256 - 1).to_bytes(32, "big"),
    ],
    ids=["twist", "field-order", "all-ones"],
)
def test_scanning_refuses_a_summary_whose_point_is_not_on_the_curve(
    prefix: int, x: bytes
) -> None:
    """The summary's point is parsed, and refused unless it is on the curve.

    The scan key is invalid on purpose: the refusal of the summary comes
    before the key is looked at, so that no summary reaches a scan key
    without being a point of secp256k1.

    Args:
        prefix: 2 or 3, the two compressed prefixes.
        x: an x coordinate with no y on the curve, or no field element.
    """
    summary = SP_OUTPOINT + bytes([prefix]) + x
    with pytest.raises(ValueError, match="invalid prevouts summary public key"):
        silentpayments.scan_outputs([SP_INPUT_PUBKEY[1:]], 0, summary, SP_SPEND_PUBKEY)


@pytest.mark.parametrize("prefix", [0, 1, 4, 5, 6, 7, 255])
def test_scanning_refuses_a_summary_with_a_bad_prefix(prefix: int) -> None:
    """Only the compressed prefixes 2 and 3 introduce a point of a summary.

    Args:
        prefix: the octet in place of the compressed prefix, over an x
            that is on the curve.
    """
    summary = sp_summary()[:36] + bytes([prefix]) + SP_INPUT_PUBKEY[1:]
    with pytest.raises(ValueError, match="invalid prevouts summary public key"):
        silentpayments.scan_outputs(
            [SP_INPUT_PUBKEY[1:]], SP_SCAN_PRVKEY, summary, SP_SPEND_PUBKEY
        )


def test_scanning_refuses_an_invalid_scan_key() -> None:
    """A scan key outside [1, n-1] is what libsecp256k1 refuses the scan for."""
    with pytest.raises(ValueError, match="silent payment scanning failed"):
        silentpayments.scan_outputs(
            [SP_INPUT_PUBKEY[1:]], 0, sp_summary(), SP_SPEND_PUBKEY
        )


@pytest.mark.parametrize(
    "labels, message",
    [
        ({bytes(33): bytes(31)}, "label tweak must be 32 bytes"),
        ({bytes(32): bytes(32)}, "label must be 33 bytes"),
        ({bytes(33): N.to_bytes(32)}, r"label tweak must be in \[1, n-1\]"),
        ({bytes(33): bytes([0xFF] * 32)}, r"label tweak must be in \[1, n-1\]"),
        ({bytes(33): bytes(32)}, r"label tweak must be in \[1, n-1\]"),
    ],
)
def test_scanning_refuses_a_malformed_label_cache(
    labels: dict[bytes, bytes], message: str
) -> None:
    """Both halves of a cache entry are checked, and before the scan starts.

    The tweak has to be copied into a buffer this package owns before the
    callback can hand a pointer to it back, so a wrong length is caught
    there rather than inside a lookup that has nowhere to raise.

    Args:
        labels: a cache with one malformed entry.
        message: what the exception has to name.
    """
    with pytest.raises(ValueError, match=message):
        silentpayments.scan_outputs(
            [SP_INPUT_PUBKEY[1:]],
            SP_SCAN_PRVKEY,
            sp_summary(),
            SP_SPEND_PUBKEY,
            labels=labels,
        )


def spy_on_wipe(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Record every buffer `silentpayments` wipes, and wipe it for real.

    The buffers holding a secret in these wrappers are locals, gone by the
    time a caller could look at one, so a spy is the only way to hold what
    was wiped and check it. What it holds is the buffer itself, wiped: the
    assertions below read it after the call.

    The spy goes onto `silentpayments` and the real one is read from
    `_secret`, which is not interchangeable: the module does
    `from ._secret import wipe`, so it holds a reference of its own and
    patching `_secret.wipe` would not reach it.

    Args:
        monkeypatch: the fixture, whose undo is what keeps this local to
            one test.

    Returns:
        The list the spy appends to, in the order the wrapper wipes.
    """
    wiped: list[object] = []

    def recording_wipe(buffer: object) -> None:
        wiped.append(buffer)
        _secret.wipe(buffer)

    monkeypatch.setattr(silentpayments, "wipe", recording_wipe)
    return wiped


def zeroed(buffer: object) -> bool:
    """Whether a cffi buffer holds nothing but zeros."""
    memory = ffi.buffer(buffer)
    return bytes(memory) == bytes(len(memory))


def test_the_sender_wipes_every_private_key_it_copied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both kinds of key are wiped, one buffer each, and on the way out.

    A taproot key becomes a `secp256k1_keypair` and any other a 32-octet
    buffer; both are memory this package owns and both carry the secret,
    so both are taken back. The count is what a loop that ran no
    iterations would fail -- which is what a mutation session turned this
    wipe into, and nothing noticed.

    Args:
        monkeypatch: the fixture the spy is installed through.
    """
    wiped = spy_on_wipe(monkeypatch)

    silentpayments.create_outputs(
        [(SP_SCAN_PUBKEY, SP_SPEND_PUBKEY)],
        SP_OUTPOINT,
        taproot_prvkeys=[SP_INPUT_PRVKEY],
        prvkeys=[SP_SPEND_PRVKEY],
    )

    assert len(wiped) == 2, "one buffer per private key given, and no more"
    assert all(zeroed(buffer) for buffer in wiped)


def test_the_sender_wipes_the_keys_it_had_when_a_later_one_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A key that cannot be made does not leave the ones before it behind.

    Which is why the two lists are built inside the `try` rather than
    before it: the second key here is invalid, so `_keypair` raises with
    the first already made, and the `finally` has to be in force for it.

    Args:
        monkeypatch: the fixture the spy is installed through.
    """
    wiped = spy_on_wipe(monkeypatch)

    with pytest.raises(ValueError, match="invalid private key"):
        silentpayments.create_outputs(
            [(SP_SCAN_PUBKEY, SP_SPEND_PUBKEY)],
            SP_OUTPOINT,
            taproot_prvkeys=[SP_INPUT_PRVKEY, 0],
        )

    assert len(wiped) == 1, "the key made before the refusal"
    assert all(zeroed(buffer) for buffer in wiped)


def test_scanning_wipes_the_tweaks_and_the_label_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every found output and the label table are taken back.

    The found outputs are wiped whether libsecp256k1 wrote to them or
    not -- the array is as long as the outputs one and it says through
    `n_found` how much of it it used -- so the count is one per
    transaction output plus one for the label table.

    Args:
        monkeypatch: the fixture the spy is installed through.
    """
    label, label_tweak = silentpayments.label(SP_SCAN_PRVKEY, 1)
    labeled = silentpayments.labeled_spend_pubkey(SP_SPEND_PUBKEY, label)
    outputs = silentpayments.create_outputs(
        [(SP_SCAN_PUBKEY, labeled), (SP_SCAN_PUBKEY, SP_SPEND_PUBKEY)],
        SP_OUTPOINT,
        prvkeys=[SP_INPUT_PRVKEY],
    )
    summary = sp_summary()
    wiped = spy_on_wipe(monkeypatch)

    found = silentpayments.scan_outputs(
        outputs, SP_SCAN_PRVKEY, summary, SP_SPEND_PUBKEY, labels={label: label_tweak}
    )

    assert len(found) == 2, "both outputs are this recipient's"
    assert len(wiped) == len(outputs) + 1, (
        "every found output slot, and the label table"
    )
    assert all(zeroed(buffer) for buffer in wiped)
    # the tweaks reached the caller before the buffers were zeroed
    assert all(tweak != bytes(32) for _, tweak, _ in found)


def test_scanning_copies_no_tweak_when_a_label_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tweak is not copied into the table before every entry is checked.

    The table is made once the whole mapping has been read, so that a
    refusal after a valid entry leaves nothing of this package's to take
    back: the one buffer wiped is the output slot. Were the table made
    first and filled entry by entry, the tweak copied before the refusal
    would be released in the clear unless something wiped it.

    Args:
        monkeypatch: the fixture the spy is installed through.
    """
    label, label_tweak = silentpayments.label(SP_SCAN_PRVKEY, 1)
    summary = sp_summary()
    wiped = spy_on_wipe(monkeypatch)

    with pytest.raises(ValueError, match="label tweak must be 32 bytes"):
        silentpayments.scan_outputs(
            [SP_INPUT_PUBKEY[1:]],
            SP_SCAN_PRVKEY,
            summary,
            SP_SPEND_PUBKEY,
            labels={label: label_tweak, bytes(silentpayments.LABEL_SIZE): bytes(31)},
        )

    assert len(wiped) == 1, "the one output slot, and no table"
    assert all(zeroed(buffer) for buffer in wiped)


def test_scanning_wipes_one_table_whatever_the_number_of_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The tweaks of any number of labels are one buffer, and it is wiped.

    An empty mapping is a table too, with a count and nothing else, and is
    wiped like the others.

    Args:
        monkeypatch: the fixture the spy is installed through.
    """
    summary = sp_summary()
    for count in (0, 1, 5):
        wiped = spy_on_wipe(monkeypatch)
        labels = dict(silentpayments.label(SP_SCAN_PRVKEY, m) for m in range(count))

        silentpayments.scan_outputs(
            [SP_INPUT_PUBKEY[1:]], SP_SCAN_PRVKEY, summary, SP_SPEND_PUBKEY, labels
        )

        assert len(wiped) == 2, "the output slot, and the one table"
        assert all(zeroed(buffer) for buffer in wiped)


def test_the_label_lookup_runs_no_python(scan_python_calls: list[int]) -> None:
    """Scanning with labels calls back into no Python, however many times.

    libsecp256k1 asks for the tweak of a candidate label twice for each
    output it checks, and at each k it checks again from the first output,
    so a lookup in Python is one crossing into the interpreter for each.
    The labeled output is found, so the lookup did run.

    Args:
        scan_python_calls: the count of Python calls, one per native scan.
    """
    label, label_tweak = silentpayments.label(SP_SCAN_PRVKEY, 1)
    outputs = silentpayments.create_outputs(
        [
            (
                SP_SCAN_PUBKEY,
                silentpayments.labeled_spend_pubkey(SP_SPEND_PUBKEY, label),
            ),
            (SP_SCAN_PUBKEY, SP_SPEND_PUBKEY),
        ],
        SP_OUTPOINT,
        prvkeys=[SP_INPUT_PRVKEY],
    )

    found = silentpayments.scan_outputs(
        outputs, SP_SCAN_PRVKEY, sp_summary(), SP_SPEND_PUBKEY, {label: label_tweak}
    )

    assert [found_label for _, _, found_label in found] == [label, None]
    assert scan_python_calls == [0]


def test_the_count_of_python_calls_sees_a_python_lookup(
    scan_python_calls: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The control of the test above: a Python lookup is counted.

    Without it a count of zero could be a spy that sees nothing. The
    output does not match the unlabeled key, so libsecp256k1 asks the
    lookup for its tweak, and the lookup answers no label: the scan finds
    nothing, and the count is the number of times it asked.

    Args:
        scan_python_calls: the count of Python calls, one per native scan.
        monkeypatch: the fixture the Python lookup is installed through.
    """
    label, label_tweak = silentpayments.label(SP_SCAN_PRVKEY, 1)
    outputs = silentpayments.create_outputs(
        [(SP_SCAN_PUBKEY, silentpayments.labeled_spend_pubkey(SP_SPEND_PUBKEY, label))],
        SP_OUTPOINT,
        prvkeys=[SP_INPUT_PRVKEY],
    )

    def lookup(_label33: object, _label_context: object) -> object:
        return ffi.NULL

    monkeypatch.setattr(
        "btclib_secp256k1.silentpayments.lib.btclib_secp256k1_label_lookup_sorted",
        ffi.callback("secp256k1_silentpayments_label_lookup", lookup),
        raising=False,
    )

    found = silentpayments.scan_outputs(
        outputs, SP_SCAN_PRVKEY, sp_summary(), SP_SPEND_PUBKEY, {label: label_tweak}
    )

    assert found == []
    assert scan_python_calls[0] > 0


def table_lookup(table: object, label: bytes) -> bytes | None:
    """Ask the C lookup for a label's tweak, as libsecp256k1 does.

    Args:
        table: the table `silentpayments._label_table` built.
        label: the 33 bytes of a candidate label.

    Returns:
        The 32-byte tweak, or None where the lookup answers NULL.
    """
    answer = lib.btclib_secp256k1_label_lookup_sorted(
        ffi.new("unsigned char[]", label), table
    )
    return None if answer == ffi.NULL else bytes(ffi.buffer(answer, 32))


def test_the_label_lookup_finds_every_label_and_only_those() -> None:
    """Binary search over the sorted table answers each label and no other.

    The labels are not points: the lookup compares 33 octets and nothing
    else, as unsigned bytes -- hence second octets on both sides of 0x80,
    which a signed comparison would order the other way. They are given
    out of order, and every one has a neighbour that differs in its last
    octet and is not in the table, as do the ends of the range. Each size
    from one to nine covers an odd and an even search, and the ends. The
    independent side is the Python `dict` the table is built from, which
    says which label has which tweak.
    """
    for size in range(1, 10):
        octets = [
            bytes([2 + index % 2, (index * 53) % 256]) + bytes([index]) * 31
            for index in range(size)
        ]
        labels = {octet: bytes([index + 1]) * 32 for index, octet in enumerate(octets)}
        table = silentpayments._label_table(labels)

        for octet, tweak in labels.items():
            assert table_lookup(table, octet) == tweak
            for neighbour in (octet[:32] + b"\x00", octet[:32] + b"\xff"):
                assert (table_lookup(table, neighbour) is None) == (
                    neighbour not in labels
                )
        below = bytes(33)
        above = b"\xff" * 33
        assert table_lookup(table, below) is None
        assert table_lookup(table, above) is None


def test_the_label_lookup_of_an_empty_table_finds_nothing() -> None:
    """A table of no label is searched, and answers NULL.

    The independent side is the empty Python `dict` it is built from.
    """
    table = silentpayments._label_table({})

    assert table_lookup(table, bytes(33)) is None
    assert bytes(ffi.buffer(table)) == bytes(ffi.sizeof("size_t"))


def test_a_label_given_twice_keeps_its_last_tweak() -> None:
    """Two keys that are the same 33 octets are one label, as in a `dict`.

    A mapping other than a `dict` can yield a `bytes` and a `bytearray`
    that are equal, and the table has the label once, with the tweak of
    the entry that came last. The independent side is the Python `dict`,
    which keeps the last of two equal keys.
    """

    class Twice(Mapping[Any, bytes]):
        @override
        def __getitem__(self, key: Any) -> bytes:
            return b"\x02" * 32 if isinstance(key, bytearray) else b"\x01" * 32

        @override
        def __iter__(self) -> Iterator[Any]:
            return iter([bytes(33), bytearray(33)])

        @override
        def __len__(self) -> int:
            return 2

    table = silentpayments._label_table(Twice())

    assert len(Twice()) == 2
    assert len(ffi.buffer(table)) == ffi.sizeof("size_t") + 33 + 32
    assert table_lookup(table, bytes(33)) == b"\x02" * 32


def test_labels_that_are_not_a_mapping_are_a_type_error() -> None:
    """A list of pairs is the likeliest wrong shape, and has no `.items()`.

    The lookup raised `AttributeError: 'list' object has no attribute
    'items'`; the argument is refused by name and type instead.
    """
    label, label_tweak = silentpayments.label(SP_SCAN_PRVKEY, 1)
    for wrong in ([(label, label_tweak)], b"x", 7):
        with pytest.raises(TypeError, match="labels must be a mapping, not"):
            silentpayments.scan_outputs(
                [SP_INPUT_PUBKEY[1:]],
                SP_SCAN_PRVKEY,
                sp_summary(),
                SP_SPEND_PUBKEY,
                labels=wrong,  # type: ignore[arg-type]
            )


@pytest.mark.parametrize("which", ["prvkeys", "taproot_prvkeys"])
@pytest.mark.parametrize(
    "bare",
    [
        pytest.param(SP_INPUT_PRVKEY, id="bytes"),
        pytest.param(bytearray(SP_INPUT_PRVKEY), id="bytearray"),
        pytest.param(memoryview(SP_INPUT_PRVKEY), id="memoryview"),
        pytest.param("k" * 32, id="str"),
        pytest.param(ffi.new("unsigned char[32]"), id="cffi array"),
        pytest.param(array.array("B", bytes(32)), id="array.array"),
        pytest.param(b"", id="empty bytes"),
    ],
)
def test_silent_payment_creation_refuses_a_bare_key(which: str, bare: object) -> None:
    """A key given alone is refused, not read as 32 one-octet keys.

    The 32 octets of a key, passed where the list goes, are 32 keys
    whose sum is below 8161, which no recipient can find the outputs of.
    The empty one is refused as a type too, before it is read as no key.
    """
    with pytest.raises(TypeError, match=f"the {which} must be a sequence of values"):
        silentpayments.create_outputs(
            [(SP_SCAN_PUBKEY, SP_SPEND_PUBKEY)],
            SP_OUTPOINT,
            **{which: bare},  # type: ignore[arg-type]
        )
