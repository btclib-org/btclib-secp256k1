# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""An invalid scalar or point never reaches secp256k1-zkp's illegal callback.

`tests/invalid_arguments_test.py` asks this of the mainline modules, and
this file asks it of the `zkp` subpackage, which reports through a
context of its own. Each public function that takes octets or integers
is driven with each invalid value that applies to each of its
arguments, every other argument keeping a valid value. Every call must
refuse, and `zkp.context.check` must find nothing afterwards.

A refusal is a `TypeError`, a `ValueError` other than the one
`zkp.context.check` raises, a `RuntimeError`, or the `False` a verdict
function answers. `generator` raises a `RuntimeError` for a blinding
factor from n up, which secp256k1-zkp refuses after `scalar` has taken
it, and `tests/zkp_generator_vectors_test.py` pins that.

The invalid values are those of the mainline test, imported from it,
and the ones the subpackage's own arguments need, defined in this file.

The table is held to the modules' own contents, by the mainline test's
rule: a public function that takes octets or integers and is not in it
fails here, and so does one of its arguments left out. A function with
a `CData` parameter is excluded.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import inspect
import pkgutil
from collections.abc import Callable
from types import ModuleType
from typing import Any

import pytest

pytest.importorskip("_btclib_secp256k1_zkp")

from btclib_secp256k1 import CData, keys, zkp
from btclib_secp256k1.zkp import context as zkp_context
from btclib_secp256k1.zkp import (
    ecdsa_adaptor,
    ecdsa_s2c,
    generator,
    musig,
    rangeproof,
)
from tests.invalid_arguments_test import (
    ADDEND,
    INTO,
    OCTETS,
    OVERFLOWING,
    POINT,
    SCALAR,
    WRONG_TYPE,
    ZERO,
    Arguments,
    Values,
    int_outside,
    last_of,
    octets_or_integers,
    valid,
)
from tests.zkp_rangeproof_vectors_test import (
    BORROMEAN_E0,
    BORROMEAN_M,
    BORROMEAN_PUBKEYS,
    BORROMEAN_RSIZES,
    BORROMEAN_S,
)

pytestmark = pytest.mark.zkp

MSG = hashlib.sha256(b"btclib_secp256k1 zkp invalid arguments").digest()
PRVKEYS = [(1).to_bytes(32, "big"), (2).to_bytes(32, "big")]
PUBKEYS = [keys.pubkey_from_prvkey(prvkey) for prvkey in PRVKEYS]
PRVKEY, PUBKEY = PRVKEYS[0], PUBKEYS[0]
DECKEY = (3).to_bytes(32, "big")
ENCKEY = keys.pubkey_from_prvkey(DECKEY)
TWEAK = (4).to_bytes(32, "big")
DATA = b"\x05" * 32
BLIND = (6).to_bytes(32, "big")
VALUE = 1000

ADAPTOR_SIG = ecdsa_adaptor.encrypt(MSG, PRVKEY, ENCKEY)
SIG = ecdsa_adaptor.decrypt(DECKEY, ADAPTOR_SIG)

S2C_SIG, S2C_OPENING = ecdsa_s2c.sign(MSG, PRVKEY, DATA)
HOST_COMMITMENT = ecdsa_s2c.anti_exfil_host_commit(DATA)
AE_OPENING = ecdsa_s2c.anti_exfil_signer_commit(MSG, PRVKEY, HOST_COMMITMENT)
AE_SIG = ecdsa_s2c.anti_exfil_sign(MSG, PRVKEY, DATA)

GEN = generator.generate(DATA)
COMMIT = generator.pedersen_commit(BLIND, VALUE)
PROOF = rangeproof.sign(COMMIT, BLIND, DATA, VALUE)

CACHE = musig.KeyAggCache(PUBKEYS)


def round_one() -> list[musig.SecretNonce]:
    """Generate one secret nonce per signer, the same ones on every call.

    Returns:
        The secret nonces, in `PRVKEYS` order, each of which signs under
        `SESSION` and `ADAPTOR_SESSION`.
    """
    return [
        musig.nonce_gen_counter(prvkey, 0, msg32=MSG, keyagg_cache=CACHE)
        for prvkey in PRVKEYS
    ]


PUBNONCES = [nonce.pubnonce for nonce in round_one()]
AGGNONCE = musig.nonce_agg(PUBNONCES)
SESSION = musig.Session(AGGNONCE, MSG, CACHE)
PARTIAL_SIGS = [
    nonce.partial_sign(prvkey, CACHE, SESSION)
    for nonce, prvkey in zip(round_one(), PRVKEYS, strict=True)
]
ADAPTOR_SESSION = musig.Session(AGGNONCE, MSG, CACHE, ENCKEY)
PRE_SIG = ADAPTOR_SESSION.partial_sig_agg([
    nonce.partial_sign(prvkey, CACHE, ADAPTOR_SESSION)
    for nonce, prvkey in zip(round_one(), PRVKEYS, strict=True)
])
PARITY = ADAPTOR_SESSION.nonce_parity()
ADAPTED = musig.adapt(PRE_SIG, DECKEY, PARITY)

# a point serialized compressed: the 65-octet one of `POINT` has the
# wrong size for it
COMPRESSED: Values = {
    label: value
    for label, value in POINT.items()
    if not isinstance(value, bytes) or len(value) == 33
}
# a sequence the library refuses with no item
EMPTY: Values = {"no item": []}


def tagged_point(prefix: int, valid_bytes: bytes) -> Values:
    """Return the invalid values of a generator or a Pedersen commitment.

    Each is a tag octet and the x of a point. x = 0 and x = 5 are not
    the x of any point, as `POINT` says.

    Args:
        prefix: the tag of a y that is a square mod p.
        valid_bytes: a valid serialization.

    Returns:
        The x of no point under the tag, a valid x under a public key's
        tag, and the wrong type.
    """
    return {
        "x = 0": bytes([prefix]) + bytes(32),
        "x = 5": bytes([prefix]) + (5).to_bytes(32, "big"),
        "a public key's tag": b"\x02" + valid_bytes[1:],
        **WRONG_TYPE,
    }


GENERATOR = tagged_point(0x0A, GEN)
COMMITMENT = tagged_point(0x08, COMMIT)


def in_place(valid_bytes: bytes, start: int, what: str, invalid: Values) -> Values:
    """Return `valid_bytes` with the 32 octets of a scalar replaced.

    Args:
        valid_bytes: the valid octets.
        start: where the octets of the scalar begin.
        what: the scalar's name, which labels each value.
        invalid: the invalid values of the scalar, as octets and as an
            int.

    Returns:
        Each invalid value given as octets put in place, and the wrong
        type for the whole.
    """
    return {
        f"{what} {label}": valid_bytes[:start] + value + valid_bytes[start + 32 :]
        for label, value in invalid.items()
        if isinstance(value, bytes)
    } | WRONG_TYPE


def a_point_at(valid_bytes: bytes, start: int, what: str) -> Values:
    """Return `valid_bytes` with the 33 octets of a compressed point replaced.

    Args:
        valid_bytes: the valid octets.
        start: where the octets of the point begin.
        what: the point's name, which labels each value.

    Returns:
        Each invalid compressed point put in place, and the wrong type
        for the whole.
    """
    return {
        f"{what} {label}": valid_bytes[:start] + value + valid_bytes[start + 33 :]
        for label, value in COMPRESSED.items()
        if isinstance(value, bytes)
    } | WRONG_TYPE


# a compact signature is r and s, scalars zero is invalid for
COMPACT_SIGNATURE = in_place(SIG, 0, "r", ZERO | OVERFLOWING) | in_place(
    SIG, 32, "s", ZERO | OVERFLOWING
)
# an adaptor signature is R, R', s' and the proof's e and s. R and R'
# are points, s' a scalar zero is invalid for, the proof's s a scalar
# from n up is invalid for, and its e any 32 octets
_S_PRIME = in_place(ADAPTOR_SIG, 66, "s'", ZERO | OVERFLOWING)
ADAPTOR_SIGNATURE = (
    a_point_at(ADAPTOR_SIG, 0, "R")
    | a_point_at(ADAPTOR_SIG, 33, "R'")
    | _S_PRIME
    | in_place(ADAPTOR_SIG, 130, "the proof's s", OVERFLOWING)
)
# decrypt and recover read only R's x, a scalar zero is invalid for,
# and s'
ADAPTOR_R_X_AND_S = {"R's x zero": b"\x02" + bytes(32) + ADAPTOR_SIG[33:]} | _S_PRIME
# a BIP340 signature, or a pre-signature: only s is parsed
SCHNORR_S = in_place(ADAPTED, 32, "s", OVERFLOWING)
PRE_SIG_S = in_place(PRE_SIG, 32, "s", OVERFLOWING)
# a public nonce is two compressed points, an aggregate nonce too
PUBNONCE = a_point_at(PUBNONCES[0], 0, "first") | a_point_at(PUBNONCES[0], 33, "second")
AGGREGATE_NONCE = a_point_at(AGGNONCE, 0, "first") | a_point_at(AGGNONCE, 33, "second")
# a partial signature is a scalar, which zero is a valid value of
PARTIAL_SIG = in_place(PARTIAL_SIGS[0], 0, "s", OVERFLOWING)
# the ring signature's s is one scalar per public key. More than 128
# public keys cannot be driven alone: `rsizes` would no longer sum to
# their number, nor `s` have their size
BORROMEAN_SIGNATURE = in_place(BORROMEAN_S, 0, "the first s", OVERFLOWING)
# a ring may be empty, so 33 rings keep the sum of the valid ones
RSIZES: Values = (
    last_of(BORROMEAN_RSIZES, int_outside(128))
    | EMPTY
    | {"summing to fewer keys": [*BORROMEAN_RSIZES[:-1], BORROMEAN_RSIZES[-1] - 1]}
    | {"33 rings": [*BORROMEAN_RSIZES, *[0] * (33 - len(BORROMEAN_RSIZES))]}
)
UINT64 = int_outside(2**64 - 1)


def signed_partially(**kwargs: Any) -> bytes:
    """Sign with the first signer's secret nonce, under `SESSION`.

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
TABLE: dict[str, tuple[Callable[..., Any], Arguments]] = {
    "ecdsa_adaptor.decrypt": (
        ecdsa_adaptor.decrypt,
        {
            "deckey": (DECKEY, SCALAR),
            "adaptor_sig162": (ADAPTOR_SIG, ADAPTOR_R_X_AND_S),
        },
    ),
    "ecdsa_adaptor.encrypt": (
        ecdsa_adaptor.encrypt,
        {
            "msg32": (MSG, OCTETS),
            "prvkey": (PRVKEY, SCALAR),
            "enckey": (ENCKEY, POINT),
            "aux_rand32": (None, OCTETS),
        },
    ),
    "ecdsa_adaptor.recover": (
        ecdsa_adaptor.recover,
        {
            "sig64": (SIG, COMPACT_SIGNATURE),
            "adaptor_sig162": (ADAPTOR_SIG, ADAPTOR_R_X_AND_S),
            "enckey": (ENCKEY, POINT),
            "into": (None, INTO),
        },
    ),
    "ecdsa_adaptor.verify": (
        ecdsa_adaptor.verify,
        {
            "adaptor_sig162": (ADAPTOR_SIG, ADAPTOR_SIGNATURE),
            "pubkey": (PUBKEY, POINT),
            "msg32": (MSG, OCTETS),
            "enckey": (ENCKEY, POINT),
        },
    ),
    "ecdsa_s2c.anti_exfil_host_commit": (
        ecdsa_s2c.anti_exfil_host_commit,
        {"rand32": (DATA, OCTETS)},
    ),
    "ecdsa_s2c.anti_exfil_host_verify": (
        ecdsa_s2c.anti_exfil_host_verify,
        {
            "signature_bytes": (AE_SIG, COMPACT_SIGNATURE),
            "msg_bytes": (MSG, OCTETS),
            "pubkey_bytes": (PUBKEY, POINT),
            "host_data32": (DATA, OCTETS),
            "opening_bytes": (AE_OPENING, COMPRESSED),
        },
    ),
    "ecdsa_s2c.anti_exfil_sign": (
        ecdsa_s2c.anti_exfil_sign,
        {
            "msg_bytes": (MSG, OCTETS),
            "prvkey": (PRVKEY, SCALAR),
            "host_data32": (DATA, OCTETS),
        },
    ),
    "ecdsa_s2c.anti_exfil_signer_commit": (
        ecdsa_s2c.anti_exfil_signer_commit,
        {
            "msg_bytes": (MSG, OCTETS),
            "prvkey": (PRVKEY, SCALAR),
            "rand_commitment32": (HOST_COMMITMENT, OCTETS),
        },
    ),
    "ecdsa_s2c.opening_parse": (
        ecdsa_s2c.opening_parse,
        {"opening_bytes": (S2C_OPENING, COMPRESSED)},
    ),
    "ecdsa_s2c.sign": (
        ecdsa_s2c.sign,
        {
            "msg_bytes": (MSG, OCTETS),
            "prvkey": (PRVKEY, SCALAR),
            "s2c_data32": (DATA, OCTETS),
        },
    ),
    "ecdsa_s2c.verify_commit": (
        ecdsa_s2c.verify_commit,
        {
            "signature_bytes": (S2C_SIG, COMPACT_SIGNATURE),
            "data32": (DATA, OCTETS),
            "opening_bytes": (S2C_OPENING, COMPRESSED),
        },
    ),
    "generator.generate": (generator.generate, {"seed32": (DATA, OCTETS)}),
    "generator.generate_blinded": (
        generator.generate_blinded,
        {"seed32": (DATA, OCTETS), "blind32": (BLIND, ADDEND)},
    ),
    "generator.parse": (generator.parse, {"generator_bytes": (GEN, GENERATOR)}),
    "generator.pedersen_blind_generator_blind_sum": (
        generator.pedersen_blind_generator_blind_sum,
        {
            "values": ([VALUE, VALUE], last_of([VALUE, VALUE], UINT64)),
            "generator_blinds": ([BLIND, BLIND], last_of([BLIND, BLIND], ADDEND)),
            "blinding_factors": ([BLIND, BLIND], last_of([BLIND, BLIND], ADDEND)),
            "n_inputs": (1, int_outside(1)),
            "into": (None, INTO),
        },
    ),
    "generator.pedersen_blind_sum": (
        generator.pedersen_blind_sum,
        {
            "blinds": ([BLIND, BLIND], last_of([BLIND, BLIND], ADDEND)),
            "npositive": (1, int_outside(2)),
            "into": (None, INTO),
        },
    ),
    "generator.pedersen_commit": (
        generator.pedersen_commit,
        {
            "blind": (BLIND, ADDEND),
            "value": (VALUE, UINT64),
            "gen_bytes": (GEN, GENERATOR),
        },
    ),
    "generator.pedersen_commitment_parse": (
        generator.pedersen_commitment_parse,
        {"commitment_bytes": (COMMIT, COMMITMENT)},
    ),
    "generator.pedersen_verify_tally": (
        generator.pedersen_verify_tally,
        {
            "commits_bytes": ([COMMIT], last_of([COMMIT], COMMITMENT)),
            "ncommits_bytes": ([COMMIT], last_of([COMMIT], COMMITMENT)),
        },
    ),
    "musig.KeyAggCache": (
        musig.KeyAggCache,
        {"pubkeys_bytes": (PUBKEYS, last_of(PUBKEYS, POINT) | EMPTY)},
    ),
    "musig.KeyAggCache.pubkey_ec_tweak_add": (
        lambda **kwargs: musig.KeyAggCache(PUBKEYS).pubkey_ec_tweak_add(**kwargs),
        {"tweak": (TWEAK, ADDEND)},
    ),
    "musig.KeyAggCache.pubkey_xonly_tweak_add": (
        lambda **kwargs: musig.KeyAggCache(PUBKEYS).pubkey_xonly_tweak_add(**kwargs),
        {"tweak": (TWEAK, ADDEND)},
    ),
    "musig.SecretNonce.partial_sign": (
        signed_partially,
        {"prvkey": (PRVKEY, SCALAR)},
    ),
    "musig.Session": (
        lambda **kwargs: musig.Session(keyagg_cache=CACHE, **kwargs),
        {
            "aggnonce_bytes": (AGGNONCE, AGGREGATE_NONCE),
            "msg32": (MSG, OCTETS),
            "adaptor_bytes": (ENCKEY, POINT),
        },
    ),
    "musig.Session.partial_sig_verify": (
        lambda **kwargs: SESSION.partial_sig_verify(keyagg_cache=CACHE, **kwargs),
        {
            "partial_sig_bytes": (PARTIAL_SIGS[0], PARTIAL_SIG),
            "pubnonce_bytes": (PUBNONCES[0], PUBNONCE),
            "pubkey_bytes": (PUBKEY, POINT),
        },
    ),
    "musig.Session.partial_sig_agg": (
        SESSION.partial_sig_agg,
        {
            "partial_sigs_bytes": (
                PARTIAL_SIGS,
                last_of(PARTIAL_SIGS, PARTIAL_SIG) | EMPTY,
            )
        },
    ),
    "musig.adapt": (
        musig.adapt,
        {
            "pre_sig64": (PRE_SIG, PRE_SIG_S),
            "sec_adaptor": (DECKEY, ADDEND),
            "nonce_parity": (PARITY, int_outside(1)),
        },
    ),
    "musig.aggnonce_parse": (
        musig.aggnonce_parse,
        {"aggnonce_bytes": (AGGNONCE, AGGREGATE_NONCE)},
    ),
    "musig.extract_adaptor": (
        musig.extract_adaptor,
        {
            "sig64": (ADAPTED, SCHNORR_S),
            "pre_sig64": (PRE_SIG, PRE_SIG_S),
            "nonce_parity": (PARITY, int_outside(1)),
            "into": (None, INTO),
        },
    ),
    "musig.nonce_agg": (
        musig.nonce_agg,
        {"pubnonces_bytes": (PUBNONCES, last_of(PUBNONCES, PUBNONCE) | EMPTY)},
    ),
    "musig.nonce_gen": (
        musig.nonce_gen,
        {
            "pubkey_bytes": (PUBKEY, POINT),
            "prvkey": (PRVKEY, SCALAR),
            "msg32": (MSG, OCTETS),
            "extra_input32": (None, OCTETS),
        },
    ),
    "musig.nonce_gen_counter": (
        musig.nonce_gen_counter,
        {
            "prvkey": (PRVKEY, SCALAR),
            "nonrepeating_cnt": (0, UINT64),
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
    "rangeproof.borromean_verify": (
        rangeproof.borromean_verify,
        {
            "e0": (BORROMEAN_E0, OCTETS),
            "s": (BORROMEAN_S, BORROMEAN_SIGNATURE),
            "m": (BORROMEAN_M, OCTETS),
            "pubkeys": (
                BORROMEAN_PUBKEYS,
                last_of(BORROMEAN_PUBKEYS, POINT) | EMPTY,
            ),
            "rsizes": (BORROMEAN_RSIZES, RSIZES),
        },
    ),
    "rangeproof.info": (rangeproof.info, {"proof": (PROOF, OCTETS)}),
    "rangeproof.max_size": (
        rangeproof.max_size,
        {"max_value": (VALUE, UINT64), "min_bits": (0, int_outside(64))},
    ),
    "rangeproof.rewind": (
        rangeproof.rewind,
        {
            "commit_bytes": (COMMIT, COMMITMENT),
            "proof": (PROOF, OCTETS),
            "nonce": (DATA, OCTETS),
            "extra_commit": (b"", OCTETS),
            "gen_bytes": (None, GENERATOR),
        },
    ),
    "rangeproof.sign": (
        rangeproof.sign,
        {
            "commit_bytes": (COMMIT, COMMITMENT),
            "blind": (BLIND, ADDEND),
            "nonce": (DATA, OCTETS),
            "value": (VALUE, UINT64),
            "min_value": (0, UINT64),
            "exp": (0, {"-2": -2, "19": 19, **WRONG_TYPE}),
            "min_bits": (0, int_outside(64)),
            "message": (b"", OCTETS),
            "extra_commit": (b"", OCTETS),
            "gen_bytes": (None, GENERATOR),
        },
    ),
    "rangeproof.verify": (
        rangeproof.verify,
        {
            "commit_bytes": (COMMIT, COMMITMENT),
            "proof": (PROOF, OCTETS),
            "extra_commit": (b"", OCTETS),
            "gen_bytes": (None, GENERATOR),
        },
    ),
}

# how `zkp.context.check` begins what it raises
ILLEGAL = "libsecp256k1-zkp illegal argument"


def not_refused(call: Callable[..., Any], kwargs: dict[str, Any]) -> str | None:
    """Say why a call did not refuse its arguments, if it did not.

    Args:
        call: the function.
        kwargs: its arguments.

    Returns:
        None where the call refused, and otherwise "not refused" or the
        message of the illegal callback, raised by the call.
    """
    try:
        answer = call(**kwargs)
    except (TypeError, RuntimeError):
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
        `zkp.context.check` raised.
    """
    # whatever an earlier test left on this thread is not this one's
    with contextlib.suppress(ValueError):
        zkp_context.check()
    found = []
    for name, (_, invalid) in arguments.items():
        for label, value in invalid.items():
            reason = not_refused(call, valid(arguments) | {name: value})
            if reason is not None:
                found.append(f"{name} {label}: {reason}")
            try:
                zkp_context.check()
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
    assert not_refused(call, valid(arguments)) == "not refused"
    zkp_context.check()


def test_a_value_reaching_libsecp256k1_zkp_is_reported() -> None:
    """The sweep reports a function that hands secp256k1-zkp what it refuses.

    The stand-in passes its nonce parity to secp256k1-zkp unchecked, and
    secp256k1-zkp reports a parity other than 0 or 1 through the illegal
    callback. The stand-in answers without raising, so the sweep reports
    both halves.
    """
    ffi, lib, ctx = zkp_context._bindings()

    def unchecked(nonce_parity: int) -> CData:
        sig64 = ffi.new("unsigned char[64]")
        lib.secp256k1_musig_adapt(ctx, sig64, PRE_SIG, DECKEY, nonce_parity)
        return sig64

    found = reaches_the_callback(unchecked, {"nonce_parity": (PARITY, {"2": 2})})
    illegal = (
        "libsecp256k1-zkp illegal argument: nonce_parity == 0 || nonce_parity == 1"
    )
    assert found == ["nonce_parity 2: not refused", f"nonce_parity 2: {illegal}"]


def test_a_refusal_carrying_the_illegal_callback_is_reported() -> None:
    """The sweep reports a refusal that is the illegal callback's report.

    The stand-in raises what `zkp.context.check` reported after its
    call, as a wrapper explaining a failed call would. That leaves
    nothing on the thread, so only the refusal says the callback fired.
    """
    ffi, lib, ctx = zkp_context._bindings()

    def raising(npositive: int) -> None:
        blind = ffi.new("unsigned char[32]", BLIND)
        blinds = ffi.new("unsigned char *[]", [blind])
        blind_out = ffi.new("unsigned char[32]")
        lib.secp256k1_pedersen_blind_sum(ctx, blind_out, blinds, 1, npositive)
        zkp_context.check()

    found = reaches_the_callback(raising, {"npositive": (1, {"2": 2})})
    assert found == ["npositive 2: libsecp256k1-zkp illegal argument: npositive <= n"]


def modules() -> list[ModuleType]:
    """Return the public modules of the `zkp` subpackage.

    Returns:
        Every module directly under `btclib_secp256k1.zkp` whose name
        has no leading underscore.
    """
    return [
        importlib.import_module(f"btclib_secp256k1.zkp.{info.name}")
        for info in pkgutil.iter_modules(zkp.__path__)
        if not info.name.startswith("_")
    ]


def public_functions() -> dict[str, Callable[..., Any]]:
    """Return every public function and method, by its qualified name.

    Returns:
        Each function a module's `__all__` names, each class there by its
        constructor, and each method of those classes whose name has no
        leading underscore.
    """
    functions: dict[str, Callable[..., Any]] = {}
    for module in modules():
        prefix = module.__name__.removeprefix("btclib_secp256k1.zkp.")
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

    A control on the census: the test above would pass on a rule that
    excluded everything, its table emptied with it.
    """
    assert octets_or_integers(generator.serialize) is None
    assert octets_or_integers(generator.parse) == {"generator_bytes"}
    assert octets_or_integers(generator.h) == set()
