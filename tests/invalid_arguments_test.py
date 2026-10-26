# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""An invalid scalar or point never reaches libsecp256k1's illegal callback.

The public functions that take octets or integers parse them first, so
libsecp256k1's illegal callback should never fire under them. This test
drives each of them with each invalid value that applies to each of its
arguments, and asks two things of every call: that it refuses, as
`tests/size_sweep_test.py`'s `refused` reads a refusal, and that the
illegal callback reported nothing. A wrapper calling libsecp256k1
through `context._checked` raises what the callback reported, so the
refusal must not be that report; every other call leaves it on the
thread, so `context.check` must find nothing afterwards.

The invalid values are a zero scalar where zero is not a valid one, a
scalar from n to 2**256 - 1, a point not on the curve, an int outside
the range of its argument, and a value of the wrong type. Every other
argument keeps a valid value, so each call isolates one invalid value.

The table is held to the modules' own contents: a public function that
takes octets or integers and is not in it fails here, and so does one
of its arguments left out. A function with a libsecp256k1 object among
its parameters (a `CData`) is excluded by rule. There is nothing to
parse before the call, and `tests/callbacks_test.py` pins what those
functions do with an object libsecp256k1 refuses.

The `zkp` subpackage is not driven: it exists only in a build made with
`BTCLIB_LIBSECP256K1_ZKP`, and it reports through a context of its own.
"""

from __future__ import annotations

import contextlib
import importlib
import inspect
import pkgutil
import re
from collections.abc import Callable
from types import ModuleType
from typing import Any

import pytest

import btclib_secp256k1
from btclib_secp256k1 import (
    CData,
    context,
    dsa,
    ecdh,
    ellswift,
    ffi,
    hashes,
    keys,
    lib,
    musig,
    recovery,
    silentpayments,
    ssa,
    xonly,
)
from btclib_secp256k1.context import ctx
from tests.bytes_like_test import (
    COMPACT,
    DER,
    ELL_A,
    ELL_B,
    MSG,
    OUTPOINT,
    PRVKEY,
    PUBKEY,
    RECID,
    RECOVERABLE,
    SCAN_PRVKEY,
    SCAN_PUBKEY,
    SP_LABEL,
    SP_LABEL_TWEAK,
    SP_OUTPUTS,
    SP_SUMMARY,
    SPEND_PUBKEY,
    SSA_SIG,
    TWEAK,
    TWEAKED,
    TWEAKED_PARITY,
    XONLY,
)
from tests.size_sweep_test import (
    AGGNONCE,
    CACHE,
    PARTIAL_SIGS,
    PUBKEYS,
    PUBNONCES,
    SESSION,
    refused,
    round_one,
)

N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
P = 2**256 - 2**32 - 977

Values = dict[str, Any]

WRONG_TYPE: Values = {"a str": "\x01" * 32}

# a scalar libsecp256k1 refuses, as octets and as an int
OVERFLOWING: Values = {
    "n": N.to_bytes(32, "big"),
    "n as an int": N,
    "2**256 - 1": b"\xff" * 32,
    "2**256 - 1 as an int": 2**256 - 1,
}
ZERO: Values = {"zero": bytes(32), "zero as an int": 0}
# a private key, or a tweak that multiplies: zero is invalid for these
SCALAR: Values = ZERO | OVERFLOWING | WRONG_TYPE
# a tweak that adds: zero adds nothing, and is valid
ADDEND: Values = OVERFLOWING | WRONG_TYPE

# x = 5 is not the x of any point: 5**3 + 7 has no square root mod p. x
# = 0 is not either, and it is the one value libsecp256k1 checks of a
# point it loads. The third keeps the generator's x and moves its y
_GENERATOR = keys.pubkey_from_prvkey(1, compressed=False)
_OFF_Y = (int.from_bytes(_GENERATOR[33:], "big") + 1) % P
POINT: Values = {
    "x = 0": b"\x02" + bytes(32),
    "x = 5": b"\x02" + (5).to_bytes(32, "big"),
    "y off the curve": _GENERATOR[:33] + _OFF_Y.to_bytes(32, "big"),
    **WRONG_TYPE,
}
XONLY_POINT: Values = {
    "x = 0": bytes(32),
    "x = 5": (5).to_bytes(32, "big"),
    **WRONG_TYPE,
}

# octets driven with the wrong type only: a message, an outpoint, entropy,
# a DER encoding (its r and s: see below) or an ElligatorSwift one, which
# every 64 octets are
OCTETS: Values = WRONG_TYPE


def int_outside(upper: int) -> Values:
    """Return the invalid values of an int argument in [0, upper].

    Args:
        upper: the largest value the argument takes.

    Returns:
        One below the range, one above it, and the wrong type.
    """
    return {"-1": -1, f"{upper + 1}": upper + 1, **WRONG_TYPE}


def halves(valid: bytes, size: int, invalid: Values) -> Values:
    """Return `valid` with each of its halves replaced by an invalid value.

    Args:
        valid: the valid octets, two values of `size` octets each.
        size: the size of each half.
        invalid: the invalid values of a half, the wrong type among them.

    Returns:
        Each invalid value of a half put in place of the first half and
        then of the second, and the wrong type for the whole.
    """
    first, second = valid[:size], valid[size:]
    return {
        **{
            f"first half {label}": value + second
            for label, value in invalid.items()
            if isinstance(value, bytes) and len(value) == size
        },
        **{
            f"second half {label}": first + value
            for label, value in invalid.items()
            if isinstance(value, bytes) and len(value) == size
        },
        **WRONG_TYPE,
    }


def last_of(valid: list[Any], invalid: Values) -> Values:
    """Return a sequence with its last item replaced by an invalid value.

    Args:
        valid: the valid sequence. An empty one gets the invalid value as
            its only item.
        invalid: the invalid values of an item.

    Returns:
        The sequences, by the label of the invalid item.
    """
    return {
        f"an item {label}": [*valid[:-1], value] for label, value in invalid.items()
    }


# an r or s of an ECDSA signature: zero is not driven, nor a DER r or s
# from n up, which libsecp256k1 parses as zero. Whether `dsa` and
# `recovery` refuse those is btclib-org/btclib-secp256k1#1272's question
COMPACT_SIGNATURE = halves(COMPACT, 32, OVERFLOWING)
RECOVERABLE_SIGNATURE = halves(RECOVERABLE, 32, OVERFLOWING)
# BIP340's r is the x of a point and its s a scalar
SSA_SIGNATURE = halves(SSA_SIG, 32, XONLY_POINT | OVERFLOWING)
# a public nonce is two compressed points, an aggregate nonce too
PUBNONCE = halves(PUBNONCES[0], 33, POINT)
AGGREGATE_NONCE = halves(AGGNONCE, 33, POINT)
# a partial signature is a scalar, which zero is a valid value of
PARTIAL_SIG: Values = {
    label: value
    for label, value in (OVERFLOWING | WRONG_TYPE).items()
    if not isinstance(value, int)
}
SUMMARY: Values = {
    f"point {label}": SP_SUMMARY[:36] + value
    for label, value in POINT.items()
    if isinstance(value, bytes) and len(value) == 33
} | WRONG_TYPE
# `into` is a buffer the caller hands in to be written
INTO: Values = WRONG_TYPE


def signed(**kwargs: Any) -> bytes:
    """Sign through a fresh `ssa.Signer`.

    Args:
        **kwargs: the arguments of `Signer.sign`.

    Returns:
        The signature.
    """
    with ssa.Signer(PRVKEY) as signer:
        return signer.sign(**kwargs)


def signed_custom(**kwargs: Any) -> bytes:
    """Sign a message of any length through a fresh `ssa.Signer`.

    Args:
        **kwargs: the arguments of `Signer.sign_custom`.

    Returns:
        The signature.
    """
    with ssa.Signer(PRVKEY) as signer:
        return signer.sign_custom(**kwargs)


def held(**kwargs: Any) -> tuple[bytes, int]:
    """Build an `ssa.Signer`, and wipe it.

    Args:
        **kwargs: the arguments of the constructor.

    Returns:
        The signer's x-only public key and its parity.
    """
    with ssa.Signer(**kwargs) as signer:
        return signer.pubkey()


def signed_partially(**kwargs: Any) -> bytes:
    """Sign with a fresh secret nonce, under the module's session.

    Args:
        **kwargs: the arguments of `SecretNonce.partial_sign` that are
            octets or integers.

    Returns:
        The partial signature.
    """
    with round_one()[0] as nonce:
        return nonce.partial_sign(keyagg_cache=CACHE, session=SESSION, **kwargs)


# every public function that takes octets or integers, with each of
# those arguments: its valid value, and the invalid values that apply.
# Each call is `call(**arguments)`, so a method is called on an object
# built for it, and a constructor is the class
Arguments = dict[str, tuple[Any, Values]]
TABLE: dict[str, tuple[Callable[..., Any], Arguments]] = {
    "dsa.is_low_r": (dsa.is_low_r, {"signature_bytes": (DER, OCTETS)}),
    "dsa.is_low_s": (dsa.is_low_s, {"signature_bytes": (DER, OCTETS)}),
    "dsa.nonce_rfc6979": (
        dsa.nonce_rfc6979,
        {
            "msg_bytes": (MSG, OCTETS),
            "prvkey": (PRVKEY, SCALAR),
            "aux_rand32": (None, OCTETS),
            "attempt": (0, int_outside(2**32 - 1)),
            "into": (None, INTO),
        },
    ),
    "dsa.normalize": (dsa.normalize, {"signature_bytes": (DER, OCTETS)}),
    "dsa.parse_compact": (
        dsa.parse_compact,
        {"signature_bytes": (COMPACT, COMPACT_SIGNATURE)},
    ),
    "dsa.parse_der": (dsa.parse_der, {"signature_bytes": (DER, OCTETS)}),
    "dsa.sign": (
        dsa.sign,
        {
            "msg_bytes": (MSG, OCTETS),
            "prvkey": (PRVKEY, SCALAR),
            "aux_rand32": (None, OCTETS),
            "pubkey": (PUBKEY, POINT),
        },
    ),
    "dsa.signature_verify": (
        dsa.signature_verify,
        {"signature_bytes": (DER, OCTETS)},
    ),
    "dsa.to_compact": (dsa.to_compact, {"signature_bytes": (DER, OCTETS)}),
    "dsa.to_der": (dsa.to_der, {"signature_bytes": (COMPACT, COMPACT_SIGNATURE)}),
    "dsa.verify": (
        dsa.verify,
        {
            "msg_bytes": (MSG, OCTETS),
            "pubkey_bytes": (PUBKEY, POINT),
            "signature_bytes": (DER, OCTETS),
        },
    ),
    "ecdh.shared_point": (
        ecdh.shared_point,
        {
            "pubkey_bytes": (PUBKEY, POINT),
            "prvkey": (PRVKEY, SCALAR),
            "into": (None, INTO),
        },
    ),
    "ecdh.shared_secret": (
        ecdh.shared_secret,
        {
            "pubkey_bytes": (PUBKEY, POINT),
            "prvkey": (PRVKEY, SCALAR),
            "into": (None, INTO),
        },
    ),
    "ellswift.create": (
        ellswift.create,
        {"prvkey": (PRVKEY, SCALAR), "aux_rand32": (None, OCTETS)},
    ),
    "ellswift.decode": (ellswift.decode, {"ell_bytes": (ELL_A, OCTETS)}),
    "ellswift.encode": (
        ellswift.encode,
        {"pubkey_bytes": (PUBKEY, POINT), "aux_rand32": (None, OCTETS)},
    ),
    "ellswift.xdh": (
        ellswift.xdh,
        {
            "ell_a_bytes": (ELL_A, OCTETS),
            "ell_b_bytes": (ELL_B, OCTETS),
            "prvkey": (PRVKEY, SCALAR),
            "party": (0, int_outside(1)),
            "into": (None, INTO),
        },
    ),
    "hashes.tagged_sha256": (
        hashes.tagged_sha256,
        {"tag_bytes": (b"TapLeaf", OCTETS), "msg_bytes": (MSG, OCTETS)},
    ),
    "keys.PubkeyTweakChain": (
        keys.PubkeyTweakChain,
        {"pubkey_bytes": (PUBKEY, POINT)},
    ),
    "keys.PubkeyTweakChain.tweak_add": (
        lambda **kwargs: keys.PubkeyTweakChain(PUBKEY).tweak_add(**kwargs),
        {"tweak": (TWEAK, ADDEND)},
    ),
    "keys.parse": (keys.parse, {"pubkey_bytes": (PUBKEY, POINT)}),
    "keys.prvkey_negate": (
        keys.prvkey_negate,
        {"prvkey": (PRVKEY, SCALAR), "into": (None, INTO)},
    ),
    "keys.prvkey_tweak_add": (
        keys.prvkey_tweak_add,
        {
            "prvkey": (PRVKEY, SCALAR),
            "tweak": (TWEAK, ADDEND),
            "into": (None, INTO),
        },
    ),
    "keys.prvkey_tweak_mul": (
        keys.prvkey_tweak_mul,
        {
            "prvkey": (PRVKEY, SCALAR),
            "tweak": (TWEAK, SCALAR),
            "into": (None, INTO),
        },
    ),
    "keys.prvkey_verify": (keys.prvkey_verify, {"prvkey": (PRVKEY, SCALAR)}),
    "keys.pubkey_cmp": (
        keys.pubkey_cmp,
        {"pubkey1_bytes": (PUBKEY, POINT), "pubkey2_bytes": (PUBKEY, POINT)},
    ),
    "keys.pubkey_combine": (
        keys.pubkey_combine,
        {"pubkeys_bytes": (PUBKEYS, last_of(PUBKEYS, POINT))},
    ),
    "keys.pubkey_from_prvkey": (
        keys.pubkey_from_prvkey,
        {"prvkey": (PRVKEY, SCALAR)},
    ),
    "keys.pubkey_negate": (keys.pubkey_negate, {"pubkey_bytes": (PUBKEY, POINT)}),
    "keys.pubkey_sort": (
        keys.pubkey_sort,
        {"pubkeys_bytes": (PUBKEYS, last_of(PUBKEYS, POINT))},
    ),
    "keys.pubkey_sum": (
        keys.pubkey_sum,
        {"pubkeys_bytes": (PUBKEYS, last_of(PUBKEYS, POINT))},
    ),
    "keys.pubkey_tweak_add": (
        keys.pubkey_tweak_add,
        {"pubkey_bytes": (PUBKEY, POINT), "tweak": (TWEAK, ADDEND)},
    ),
    "keys.pubkey_tweak_mul": (
        keys.pubkey_tweak_mul,
        {"pubkey_bytes": (PUBKEY, POINT), "tweak": (TWEAK, SCALAR)},
    ),
    "keys.pubkey_tweak_mul_sum": (
        keys.pubkey_tweak_mul_sum,
        {
            "pubkeys_bytes": (PUBKEYS, last_of(PUBKEYS, POINT)),
            "tweaks": ([TWEAK, TWEAK], last_of([TWEAK, TWEAK], SCALAR)),
        },
    ),
    "keys.pubkey_verify": (keys.pubkey_verify, {"pubkey_bytes": (PUBKEY, POINT)}),
    "keys.reserialize": (keys.reserialize, {"pubkey_bytes": (PUBKEY, POINT)}),
    "musig.KeyAggCache": (
        musig.KeyAggCache,
        {"pubkeys_bytes": (PUBKEYS, last_of(PUBKEYS, POINT))},
    ),
    "musig.KeyAggCache.pubkey_ec_tweak_add": (
        lambda **kwargs: musig.KeyAggCache(PUBKEYS).pubkey_ec_tweak_add(**kwargs),
        {"tweak": (TWEAK, ADDEND)},
    ),
    "musig.KeyAggCache.pubkey_xonly_tweak_add": (
        lambda **kwargs: musig.KeyAggCache(PUBKEYS).pubkey_xonly_tweak_add(**kwargs),
        {"tweak": (TWEAK, ADDEND)},
    ),
    "musig.SecretNonce.partial_sign": (signed_partially, {"prvkey": (1, SCALAR)}),
    "musig.Session": (
        lambda **kwargs: musig.Session(keyagg_cache=CACHE, **kwargs),
        {"aggnonce_bytes": (AGGNONCE, AGGREGATE_NONCE), "msg32": (MSG, OCTETS)},
    ),
    "musig.Session.partial_sig_verify": (
        lambda **kwargs: SESSION.partial_sig_verify(keyagg_cache=CACHE, **kwargs),
        {
            "partial_sig_bytes": (PARTIAL_SIGS[0], PARTIAL_SIG),
            "pubnonce_bytes": (PUBNONCES[0], PUBNONCE),
            "pubkey_bytes": (PUBKEYS[0], POINT),
        },
    ),
    "musig.Session.partial_sig_agg": (
        SESSION.partial_sig_agg,
        {"partial_sigs_bytes": (PARTIAL_SIGS, last_of(PARTIAL_SIGS, PARTIAL_SIG))},
    ),
    "musig.aggnonce_parse": (
        musig.aggnonce_parse,
        {"aggnonce_bytes": (AGGNONCE, AGGREGATE_NONCE)},
    ),
    "musig.nonce_agg": (
        musig.nonce_agg,
        {"pubnonces_bytes": (PUBNONCES, last_of(PUBNONCES, PUBNONCE))},
    ),
    "musig.nonce_gen": (
        musig.nonce_gen,
        {
            "pubkey_bytes": (PUBKEYS[0], POINT),
            "prvkey": (1, SCALAR),
            "msg32": (MSG, OCTETS),
            "extra_input32": (None, OCTETS),
        },
    ),
    "musig.nonce_gen_counter": (
        musig.nonce_gen_counter,
        {
            "prvkey": (1, SCALAR),
            "nonrepeating_cnt": (0, int_outside(2**64 - 1)),
            "msg32": (MSG, OCTETS),
            "extra_input32": (None, OCTETS),
        },
    ),
    "musig.partial_sig_parse": (
        musig.partial_sig_parse,
        {"partial_sig_bytes": (PARTIAL_SIGS[0], PARTIAL_SIG)},
    ),
    "musig.pubnonce_parse": (
        musig.pubnonce_parse,
        {"pubnonce_bytes": (PUBNONCES[0], PUBNONCE)},
    ),
    "recovery.parse_compact": (
        recovery.parse_compact,
        {
            "signature_bytes": (RECOVERABLE, RECOVERABLE_SIGNATURE),
            "recid": (RECID, int_outside(3)),
        },
    ),
    "recovery.recover": (
        recovery.recover,
        {
            "msg_bytes": (MSG, OCTETS),
            "signature_bytes": (RECOVERABLE, RECOVERABLE_SIGNATURE),
            "recid": (RECID, int_outside(3)),
        },
    ),
    "recovery.sign": (
        recovery.sign,
        {
            "msg_bytes": (MSG, OCTETS),
            "prvkey": (PRVKEY, SCALAR),
            "aux_rand32": (None, OCTETS),
            "pubkey": (PUBKEY, POINT),
        },
    ),
    "recovery.to_der": (
        recovery.to_der,
        {
            "signature_bytes": (RECOVERABLE, RECOVERABLE_SIGNATURE),
            "recid": (RECID, int_outside(3)),
        },
    ),
    "silentpayments.create_outputs": (
        silentpayments.create_outputs,
        {
            "recipients_bytes": (
                [(SCAN_PUBKEY, SPEND_PUBKEY)],
                {
                    f"scan public key {label}": [(value, SPEND_PUBKEY)]
                    for label, value in POINT.items()
                }
                | {
                    f"spend public key {label}": [(SCAN_PUBKEY, value)]
                    for label, value in POINT.items()
                },
            ),
            "outpoint_smallest36": (OUTPOINT, OCTETS),
            "taproot_prvkeys": ((), last_of([], SCALAR)),
            "prvkeys": ([PRVKEY], last_of([PRVKEY], SCALAR)),
        },
    ),
    "silentpayments.label": (
        silentpayments.label,
        {"scan_prvkey": (SCAN_PRVKEY, SCALAR), "m": (0, int_outside(2**32 - 1))},
    ),
    "silentpayments.labeled_spend_pubkey": (
        silentpayments.labeled_spend_pubkey,
        {"spend_pubkey_bytes": (SPEND_PUBKEY, POINT), "label_bytes": (SP_LABEL, POINT)},
    ),
    "silentpayments.parse_label": (
        silentpayments.parse_label,
        {"label_bytes": (SP_LABEL, POINT)},
    ),
    "silentpayments.prevouts_summary": (
        silentpayments.prevouts_summary,
        {
            "outpoint_smallest36": (OUTPOINT, OCTETS),
            "taproot_pubkeys_bytes": ((), last_of([], XONLY_POINT)),
            "pubkeys_bytes": ([PUBKEY], last_of([PUBKEY], POINT)),
        },
    ),
    "silentpayments.scan_outputs": (
        silentpayments.scan_outputs,
        {
            "tx_outputs_bytes": (SP_OUTPUTS, last_of(SP_OUTPUTS, XONLY_POINT)),
            "scan_prvkey": (SCAN_PRVKEY, SCALAR),
            "summary_bytes": (SP_SUMMARY, SUMMARY),
            "spend_pubkey_bytes": (SPEND_PUBKEY, POINT),
            "labels": (
                {SP_LABEL: SP_LABEL_TWEAK},
                {
                    f"a tweak {label}": {SP_LABEL: value}
                    for label, value in SCALAR.items()
                },
            ),
        },
    ),
    "ssa.Signer": (held, {"prvkey": (PRVKEY, SCALAR)}),
    "ssa.Signer.sign": (
        signed,
        {"msg_bytes": (MSG, OCTETS), "aux_rand32": (None, OCTETS)},
    ),
    "ssa.Signer.sign_custom": (
        signed_custom,
        {"msg_bytes": (MSG, OCTETS), "aux_rand32": (None, OCTETS)},
    ),
    "ssa.nonce_bip340": (
        ssa.nonce_bip340,
        {
            "msg_bytes": (MSG, OCTETS),
            "prvkey": (PRVKEY, SCALAR),
            "aux_rand32": (None, OCTETS),
            "into": (None, INTO),
        },
    ),
    "ssa.sign": (
        ssa.sign,
        {
            "msg_bytes": (MSG, OCTETS),
            "prvkey": (PRVKEY, SCALAR),
            "aux_rand32": (None, OCTETS),
        },
    ),
    "ssa.sign_custom": (
        ssa.sign_custom,
        {
            "msg_bytes": (b"a message", OCTETS),
            "prvkey": (PRVKEY, SCALAR),
            "aux_rand32": (None, OCTETS),
        },
    ),
    "ssa.verify": (
        ssa.verify,
        {
            "msg_bytes": (MSG, OCTETS),
            "pubkey_bytes": (XONLY, XONLY_POINT),
            "signature_bytes": (SSA_SIG, SSA_SIGNATURE),
        },
    ),
    "xonly.from_prvkey": (xonly.from_prvkey, {"prvkey": (PRVKEY, SCALAR)}),
    "xonly.from_pubkey": (xonly.from_pubkey, {"pubkey_bytes": (PUBKEY, POINT)}),
    "xonly.parse": (xonly.parse, {"pubkey_bytes": (XONLY, XONLY_POINT)}),
    "xonly.prvkey_tweak_add": (
        xonly.prvkey_tweak_add,
        {
            "prvkey": (PRVKEY, SCALAR),
            "tweak": (TWEAK, ADDEND),
            "into": (None, INTO),
        },
    ),
    "xonly.pubkey_verify": (
        xonly.pubkey_verify,
        {"pubkey_bytes": (XONLY, XONLY_POINT)},
    ),
    "xonly.to_pubkey": (xonly.to_pubkey, {"pubkey_bytes": (XONLY, XONLY_POINT)}),
    "xonly.tweak_add": (
        xonly.tweak_add,
        {"pubkey_bytes": (XONLY, XONLY_POINT), "tweak": (TWEAK, ADDEND)},
    ),
    "xonly.tweak_add_check": (
        xonly.tweak_add_check,
        {
            "tweaked_pubkey_bytes": (TWEAKED, XONLY_POINT),
            "tweaked_parity": (TWEAKED_PARITY, int_outside(1)),
            "pubkey_bytes": (XONLY, XONLY_POINT),
            "tweak": (TWEAK, ADDEND),
        },
    ),
}


def valid(arguments: Arguments) -> dict[str, Any]:
    """Return the valid value of each argument.

    Args:
        arguments: an entry of `TABLE`.

    Returns:
        The keyword arguments of a call that is not refused.
    """
    return {name: value for name, (value, _) in arguments.items()}


# how `context.check` and `context._checked` begin what they raise
ILLEGAL = "libsecp256k1 illegal argument"


def not_refused(call: Callable[..., Any], kwargs: dict[str, Any]) -> str | None:
    """Say why a call did not refuse its arguments, if it did not.

    A refusal is what `tests/size_sweep_test.py`'s `refused` reads as
    one, except a `ValueError` raised from the illegal callback: the
    wrappers that call libsecp256k1 through `context._checked` raise
    what it reported, and leave nothing for `context.check` to find.

    Args:
        call: the function.
        kwargs: its arguments.

    Returns:
        None where the call refused, and otherwise "not refused" or the
        message of the illegal callback.
    """
    try:
        answer = call(**kwargs)
    except TypeError:
        return None
    except ValueError as error:
        return str(error) if str(error).startswith(ILLEGAL) else None
    return None if answer is False else "not refused"


def reaches_the_callback(call: Callable[..., Any], arguments: Arguments) -> list[str]:
    """Drive a function with each invalid value, and say what got through.

    Args:
        call: the function.
        arguments: its arguments, as `TABLE` gives them.

    Returns:
        One line for each invalid value that was not refused, that was
        refused with the message of the illegal callback, or after which
        `context.check` raised.
    """
    # whatever an earlier test left on this thread is not this one's
    with contextlib.suppress(ValueError):
        context.check()
    found = []
    for name, (_, invalid) in arguments.items():
        for label, value in invalid.items():
            reason = not_refused(call, valid(arguments) | {name: value})
            if reason is not None:
                found.append(f"{name} {label}: {reason}")
            try:
                context.check()
            except ValueError as error:
                found.append(f"{name} {label}: {error}")
    return found


@pytest.mark.parametrize("name", sorted(TABLE))
def test_every_invalid_value_is_refused_without_the_illegal_callback(name: str) -> None:
    """Each invalid value is refused, and the illegal callback stays silent."""
    call, arguments = TABLE[name]
    assert reaches_the_callback(call, arguments) == []


@pytest.mark.parametrize("name", sorted(TABLE))
def test_every_valid_call_is_answered(name: str) -> None:
    """The call with every argument valid is not refused.

    Without it an entry whose valid values are wrong refuses every
    invalid value too, and the test above reads that as a refusal.
    """
    call, arguments = TABLE[name]
    assert not refused(call, (), valid(arguments))
    context.check()


def test_a_value_reaching_libsecp256k1_is_reported() -> None:
    """The sweep reports a function that hands libsecp256k1 what it refuses.

    The stand-in passes its recovery id to libsecp256k1 unchecked, and
    libsecp256k1 reports a recovery id outside [0, 3] through the
    illegal callback. The stand-in answers without raising, so the sweep
    reports both halves.
    """

    def unchecked(recid: int) -> CData:
        signature = ffi.new("secp256k1_ecdsa_recoverable_signature *")
        lib.secp256k1_ecdsa_recoverable_signature_parse_compact(
            ctx, signature, RECOVERABLE, recid
        )
        return signature

    found = reaches_the_callback(unchecked, {"recid": (RECID, {"4": 4})})
    assert found == [
        "recid 4: not refused",
        "recid 4: libsecp256k1 illegal argument: recid >= 0 && recid <= 3",
    ]


def test_a_value_reaching_a_checked_call_is_reported() -> None:
    """The sweep reports the callback a wrapper raises through `_checked`.

    `keys._pubkey_sum_` takes the parsed keys on trust, and a
    `secp256k1_pubkey` nothing has written to reaches libsecp256k1,
    which reports it. `context._checked` raises that report, so it is in
    the refusal rather than on the thread.
    """

    def summed(pubkey: CData) -> CData | None:
        return keys._pubkey_sum_([pubkey])

    unwritten = ffi.new("secp256k1_pubkey *")
    found = reaches_the_callback(summed, {"pubkey": (None, {"unwritten": unwritten})})
    assert found == [
        "pubkey unwritten: libsecp256k1 illegal argument: !secp256k1_fe_is_zero(&ge->x)"
    ]


def mainline() -> list[ModuleType]:
    """Return the public modules of the package, the subpackage left out.

    Returns:
        Every module directly under `btclib_secp256k1` whose name has no
        leading underscore.
    """
    return [
        importlib.import_module(f"btclib_secp256k1.{info.name}")
        for info in pkgutil.iter_modules(btclib_secp256k1.__path__)
        if not info.ispkg and not info.name.startswith("_")
    ]


def public_functions() -> dict[str, Callable[..., Any]]:
    """Return every public function and method, by its qualified name.

    Returns:
        Each function a module's `__all__` names, each class there by its
        constructor, and each method of those classes whose name has no
        leading underscore.
    """
    functions: dict[str, Callable[..., Any]] = {}
    for module in mainline():
        prefix = module.__name__.removeprefix("btclib_secp256k1.")
        for name in module.__all__:
            member = getattr(module, name)
            if inspect.isfunction(member):
                functions[f"{prefix}.{name}"] = member
            elif inspect.isclass(member):
                functions[f"{prefix}.{name}"] = member.__init__
                functions |= {
                    f"{prefix}.{name}.{method}": function
                    for method, function in vars(member).items()
                    if inspect.isfunction(function) and not method.startswith("_")
                }
    return functions


def octets_or_integers(function: Callable[..., Any]) -> set[str] | None:
    """Return the parameters of a function that take octets or integers.

    Args:
        function: the function.

    Returns:
        The names of its parameters annotated with `BytesLike` or `int`,
        or None where any parameter is annotated with `CData`.
    """
    annotations = [
        (parameter.name, str(parameter.annotation))
        for parameter in inspect.signature(function).parameters.values()
    ]
    if any("CData" in annotation for _, annotation in annotations):
        return None
    return {
        name
        for name, annotation in annotations
        if re.search(r"BytesLike|\bint\b", annotation)
    }


def test_the_table_is_whole() -> None:
    """Every public function taking octets or integers is listed, with each.

    A function with a `CData` parameter is excluded by rule, and so is
    one that takes neither octets nor integers. The table names nothing
    else, and, for each function, exactly the parameters that take
    octets or integers.
    """
    expected = {}
    for name, function in public_functions().items():
        parameters = octets_or_integers(function)
        if parameters:
            expected[name] = parameters
    listed = {name: set(arguments) for name, (_, arguments) in TABLE.items()}
    assert listed == expected


def test_the_rule_excludes_what_takes_an_object() -> None:
    """The rule reads a `CData` parameter, and a function with none is kept.

    A control on `octets_or_integers`: the test above would pass on a
    rule that excluded everything, its table emptied with it.
    """
    assert octets_or_integers(keys.serialize) is None
    assert octets_or_integers(keys.pubkey_from_prvkey) == {"prvkey"}
    assert octets_or_integers(ssa.Signer.wipe) == set()
