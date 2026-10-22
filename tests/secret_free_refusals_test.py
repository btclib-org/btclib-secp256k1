# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""A refusal carries no secret: each key, tweak and nonce parameter is fed one.

This file tests the rule of section 7 of the btclib-org standard, *A
refusal carries no secret*, for the refusals of secret inputs.

`SCALARS` and `ENTROPIES` feed a secret, in each wrong way, to each
parameter that takes a private key, a keypair, a tweak, the label tweaks
of a scan, a nonce or its randomness, and read the refusal. `SECNONCES`
feeds it in each wrong way as the native secret nonce of a `SecretNonce`.
The census fails for such a parameter of the public API that no table
feeds. `BARE` feeds a secret where a list or a mapping of them belongs, at
a length the call refuses: at a matching length some take it as a list of
one-byte values (btclib-org/btclib-secp256k1#1228,
btclib-org/btclib-secp256k1#1229). `VALID_SECRETS` holds some refusals a
good secret reaches, which a wrong argument cannot. `PUBLIC_POSITIONS`
puts a secret where a public key, a signature, a public nonce or a label
belongs. A wiped signer, and a secret nonce spent or held with the wrong
key, are refused without quoting the key or the nonce. The other arguments
of each call are good ones: a refusal of another argument is read only
where `VALID_SECRETS` holds it. Each refusal is checked against the value
fed, the secrets its row names, `IN_PLAY`, the secrets every call here may
hold, and `DRAWN`, the secret nonces of the session a row signs in.
`assert_free` looks for each of them as `assert_secret_free` does, and for
the decimal of its bytes. `tests/zkp_secret_free_test.py` holds the same
tables for the zkp subpackage, and the same nonce cases for its MuSig2
module.

A call that returns fails the test, so no row passes without a refusal to
read. The refusals of `SCALARS`, `ENTROPIES` and `PUBLIC_POSITIONS` also
have to say which argument they refuse, in the wording the source gives it
(`ORDER` for a key at the order). Where `ORDER` holds this package's
message for a call libsecp256k1 failed, the refusal names no argument. The
two lists of `silentpayments.create_outputs` share one message, and so do
the two lists of zkp's `pedersen_blind_generator_blind_sum` at the order.
`keys.prvkey_tweak_add` and `keys.prvkey_tweak_mul` refuse a key or a
tweak at the order with one message that names both. `VALID_SECRETS`
checks no wording.
"""

from __future__ import annotations

import hashlib
import inspect
import re
import types
from importlib import import_module
from pkgutil import iter_modules
from typing import TYPE_CHECKING, Any, cast

import pytest

import btclib_secp256k1
from btclib_secp256k1 import (
    dsa,
    ecdh,
    ellswift,
    ffi,
    keys,
    musig,
    recovery,
    silentpayments,
    ssa,
    xonly,
)
from btclib_secp256k1.context import check

from .secret_free import assert_secret_free

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

#: The secret fed. A hash, so that it is a fixed random value and not a run
#: of one byte, which the helper's pieces would find in a clean message.
SECRET = hashlib.sha256(b"btclib_secp256k1 secret_free").digest()
SECRET_INT = int.from_bytes(SECRET, "big")

#: The order of the group.
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

#: Good arguments for the positions that do not hold the secret.
OTHER = hashlib.sha256(b"btclib_secp256k1 secret_free other").digest()
TWEAK = hashlib.sha256(b"btclib_secp256k1 secret_free tweak").digest()
AUX = hashlib.sha256(b"btclib_secp256k1 secret_free aux").digest()
MSG = hashlib.sha256(b"btclib_secp256k1 secret_free message").digest()
PUB = keys.pubkey_from_prvkey(OTHER)
SECRET_PUB = keys.pubkey_from_prvkey(SECRET)
XONLY, _PARITY = xonly.from_pubkey(PUB)
ELL_A = ellswift.create(OTHER, AUX)
ELL_B = ellswift.create(TWEAK, AUX)
LABEL, LABEL_TWEAK = silentpayments.label(OTHER, 0)

#: The secrets the calls here hold besides the value fed: the keys, the
#: tweak, the signing entropy and the label tweak.
IN_PLAY: list[str | bytes] = [SECRET, OTHER, TWEAK, AUX, LABEL_TWEAK]

#: What the "pointer" row points at, held here so that the collector does
#: not free it and leave the pointer reading other bytes.
POINTEE = ffi.new("unsigned char[32]", SECRET)

#: The wrong ways to hand a 32-byte secret to a position that takes it,
#: whatever the position is: by type and by size.
WRONG = {
    "hex": SECRET.hex(),
    "upper hex": SECRET.hex().upper(),
    "short": SECRET[:-1],
    "long": SECRET + b"\x01",
    "long bytearray": bytearray(SECRET + b"\x01"),
    "wide memoryview": memoryview(SECRET).cast("I"),
    "list of ints": list(SECRET),
    "float": float(SECRET_INT),
    "long cdata": ffi.new("unsigned char[33]", SECRET + b"\x01"),
    "wide cdata": ffi.new("uint32_t[8]", list(memoryview(SECRET).cast("I"))),
    "pointer": ffi.new("unsigned char **", POINTEE),
}

#: The same for a position that takes a scalar, which also takes an int and
#: refuses a value that is no key.
WRONG_SCALAR = {
    **WRONG,
    "big int": SECRET_INT + 2**256,
    "negative int": -SECRET_INT,
    "at the order": (N + SECRET_INT % 2**100).to_bytes(32, "big"),
}

#: The same for a position that takes entropy, where any 32 octets are good,
#: so the range rows are no refusal, and where an int, which a scalar
#: position takes, is one.
WRONG_ENTROPY = {**WRONG, "int": SECRET_INT}


def contents(value: object) -> object:
    """Return what a value of the wrong tables holds, to compare it later.

    Args:
        value: a value of `WRONG_SCALAR` or `WRONG_ENTROPY`.

    Returns:
        The value itself where it cannot change; otherwise its octets, or,
        for a pointer, the address and the octets it points at.
    """
    if isinstance(value, (bytes, str, int, float)):
        return value
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    if isinstance(value, list):
        return tuple(value)
    if ffi.typeof(value).kind == "pointer":
        pointee = cast("Any", value)[0]
        pointed = b"" if pointee == ffi.NULL else bytes(ffi.buffer(pointee, 32))
        return bytes(ffi.buffer(value)), pointed
    return bytes(ffi.buffer(value))


@pytest.fixture(autouse=True)
def wrong_values_unchanged() -> Iterator[None]:
    """Fail a test that changes a value of the wrong tables.

    The values are shared by every row, so a call that wipes one would
    feed the next rows something else: zeros, or a null pointer.

    Yields:
        Nothing: the test runs in between.
    """
    tables = {**WRONG_SCALAR, **WRONG_ENTROPY}
    before = {name: contents(value) for name, value in tables.items()}
    yield
    assert {name: contents(value) for name, value in tables.items()} == before


def assert_free(exc: BaseException, secrets: list[str | bytes]) -> None:
    """Assert that a refusal holds no secret, its decimal included.

    `assert_secret_free` looks for bytes as hex and as their repr. A
    scalar is also printed as a decimal, so that is looked for too.

    Args:
        exc: the refusal.
        secrets: the secrets in play in the call.
    """
    decimals = [
        str(int.from_bytes(secret, "big"))
        for secret in secrets
        if isinstance(secret, bytes) and secret
    ]
    assert_secret_free(exc, [*secrets, *decimals])


def spellings(value: object) -> list[str | bytes]:
    """Return every spelling of the secret that a value fed holds.

    Args:
        value: what was fed in place of the secret.

    Returns:
        The secret as bytes, as hex and as a decimal, and the value fed as
        the text a refusal could print of it.
    """
    spelled: list[str | bytes] = [SECRET, SECRET.hex(), str(SECRET_INT)]
    if isinstance(value, (bytes, bytearray)):
        spelled.append(bytes(value))
    elif isinstance(value, memoryview):
        spelled += [bytes(value), str(value.tolist())]
    elif isinstance(value, str):
        spelled.append(value)
    elif isinstance(value, int):
        spelled += [str(value), f"{value:x}"]
    elif isinstance(value, list):
        spelled += [bytes(value), str(value)]
    elif isinstance(value, float):
        spelled.append(str(value))
    elif ffi.typeof(value).kind == "array":
        spelled += [bytes(ffi.buffer(value)), str(list(cast("Any", value)))]
    return spelled


#: The parameters that hold a private key, a keypair, a tweak, the label
#: tweaks of a scan, a blinding factor, a decryption key or an adaptor
#: secret, and those that hold a nonce or the randomness of one.
SCALAR_PARAMETERS = re.compile(
    r"prvkey|^tweaks?$|^labels$|blind|deckey|sec_adaptor|keypair"
)
ENTROPY_PARAMETERS = re.compile(
    r"aux_rand32|^rand32$|host_data32|extra_input32|^nonce$|^secnonce$"
)


def secret_entry_points(
    modules: list[types.ModuleType],
) -> dict[str, tuple[list[str], list[str]]]:
    """Find the public entry points that take a secret, by their parameters.

    Args:
        modules: the modules whose public functions, classes and methods
            are read.

    Returns:
        Each such entry point by its dotted name, with its parameters that
        take a private key or a tweak, and those that take a nonce.
    """
    found: dict[str, tuple[list[str], list[str]]] = {}

    def read(name: str, function: Callable[..., object]) -> None:
        parameters = list(inspect.signature(function).parameters)
        scalars = [p for p in parameters if SCALAR_PARAMETERS.search(p)]
        entropies = [p for p in parameters if ENTROPY_PARAMETERS.search(p)]
        if scalars or entropies:
            found[name] = (scalars, entropies)

    for module in modules:
        short = module.__name__.removeprefix("btclib_secp256k1.")
        functions = [
            (name, member)
            for name, member in inspect.getmembers(module, inspect.isfunction)
            if member.__module__ == module.__name__ and not name.startswith("_")
        ]
        classes = [
            (name, member)
            for name, member in inspect.getmembers(module, inspect.isclass)
            if member.__module__ == module.__name__ and not name.startswith("_")
        ]
        for name, function in functions:
            read(f"{short}.{name}", function)
        for name, cls in classes:
            read(f"{short}.{name}", cls.__init__)
            methods = inspect.getmembers(
                cls, lambda m: inspect.isfunction(m) or inspect.ismethod(m)
            )
            for method_name, method in methods:
                if not method_name.startswith("_"):
                    read(f"{short}.{name}.{method_name}", method)
    return found


def package_modules(package: types.ModuleType) -> list[types.ModuleType]:
    """Return the public modules a package holds, its subpackages left out.

    Args:
        package: the package to read.

    Returns:
        Each module that is not a package and has a public name.
    """
    return [
        import_module(f"{package.__name__}.{info.name}")
        for info in iter_modules(package.__path__)
        if not info.ispkg and not info.name.startswith("_")
    ]


def untested(
    found: dict[str, tuple[list[str], list[str]]],
    scalars: dict[str, Any],
    entropies: dict[str, Any],
) -> list[str]:
    """Return the secret parameters that no table feeds.

    A table's entry is the dotted name followed by the parameter, or the
    dotted name alone where the entry point has one parameter of the kind.

    Args:
        found: `secret_entry_points`' answer.
        scalars: the table of private keys and tweaks.
        entropies: the table of nonces.

    Returns:
        Each dotted name and parameter that lacks an entry.
    """
    return [
        f"{name} {parameter}"
        for name, kinds in found.items()
        for table, parameters in zip((scalars, entropies), kinds, strict=True)
        for parameter in parameters
        if f"{name} {parameter}" not in table
        and not (len(parameters) == 1 and name in table)
    ]


def refused(call: Callable[[], object], phrases: tuple[str, ...]) -> BaseException:
    """Return the refusal a call ends in, which has to say which argument.

    Args:
        call: the call, with the secret in the position under test.
        phrases: the wordings the source gives that refusal; one of them
            has to be in it.

    Returns:
        The exception raised.
    """
    with pytest.raises((TypeError, ValueError, RuntimeError)) as caught:
        call()
    assert any(phrase in str(caught.value) for phrase in phrases)
    return caught.value


def prvkey_tweak_add_cancelling() -> object:
    """Add to the secret the tweak that makes the sum zero.

    Returns:
        Never: the sum is no key, and the call refuses it.
    """
    return keys.prvkey_tweak_add(SECRET, (N - SECRET_INT).to_bytes(32, "big"))


def xonly_prvkey_tweak_add_cancelling() -> object:
    """Add to the secret the tweak that makes the x-only sum zero.

    Returns:
        Never: the sum is no key, and the call refuses it.
    """
    _, parity = xonly.from_prvkey(SECRET)
    effective = N - SECRET_INT if parity else SECRET_INT
    return xonly.prvkey_tweak_add(SECRET, (N - effective).to_bytes(32, "big"))


def two_of_two_session(module: types.ModuleType = musig) -> tuple[Any, list[Any], Any]:
    """Build a 2-of-2 session in which the secret is the first signer's key.

    Args:
        module: the MuSig2 module, this package's or zkp's.

    Returns:
        The key aggregation, each signer's secret nonce, and the session.
    """
    prvkeys = [SECRET, OTHER]
    pubkeys = [keys.pubkey_from_prvkey(prvkey) for prvkey in prvkeys]
    cache = module.KeyAggCache(pubkeys)
    secnonces = [
        module.nonce_gen(pubkey, prvkey, msg32=MSG, keyagg_cache=cache)
        for prvkey, pubkey in zip(prvkeys, pubkeys, strict=True)
    ]
    aggnonce = module.nonce_agg([secnonce.pubnonce for secnonce in secnonces])
    return cache, secnonces, module.Session(aggnonce, MSG, cache)


#: The secret nonces of the session the last row signed in, which are in
#: play in its call.
DRAWN: list[str | bytes] = []


def partial_sign_with(prvkey: object, module: types.ModuleType = musig) -> object:
    """Sign for the first signer of a fresh 2-of-2 session.

    Args:
        prvkey: the private key to sign with.
        module: the MuSig2 module, this package's or zkp's.

    Returns:
        The partial signature.
    """
    cache, secnonces, session = two_of_two_session(module)
    DRAWN[:] = [nonce_memory(secnonce) for secnonce in secnonces]
    return secnonces[0].partial_sign(prvkey, cache, session)


def secret_nonce_with(secnonce: object, module: types.ModuleType = musig) -> object:
    """Sign for the first signer of a fresh 2-of-2 session with a secret nonce.

    Args:
        secnonce: what is passed to `SecretNonce` as the native secret
            nonce.
        module: the MuSig2 module, this package's or zkp's.

    Returns:
        The partial signature.
    """
    cache, secnonces, session = two_of_two_session(module)
    DRAWN[:] = [nonce_memory(drawn) for drawn in secnonces]
    good = secnonces[0]
    secret_nonce = module.SecretNonce(secnonce, good._pubnonce, good._pubkey)
    return secret_nonce.partial_sign(SECRET, cache, session)


def own_copy(value: object) -> object:
    """Return a value of `WRONG` that can be written to as a copy.

    `partial_sign` wipes the secret nonce it is given, so a shared array
    fed there would be zeros, and a shared pointer null, for every later
    row.

    Args:
        value: a value of `WRONG`.

    Returns:
        A new bytearray, cffi array or pointer to the same octets, or the
        value itself where nothing can write to it.
    """
    if isinstance(value, bytearray):
        return bytearray(value)
    if isinstance(value, (bytes, memoryview, str, int, float, list)):
        return value
    if ffi.typeof(value).kind == "array":
        return ffi.new(ffi.typeof(value), list(cast("Any", value)))
    # the one cdata of `WRONG` that is not an array is its pointer
    return ffi.new(ffi.typeof(value), cast("Any", value)[0])


def nonce_memory(secnonce: Any) -> bytes:
    """Return the octets of the secret nonce a `SecretNonce` holds.

    Args:
        secnonce: the nonce, not yet spent.

    Returns:
        Its octets.
    """
    held = secnonce._secnonce
    assert held is not None
    return bytes(ffi.buffer(held))


def spent_nonce(
    module: types.ModuleType = musig,
) -> tuple[BaseException, list[str | bytes]]:
    """Sign twice with one secret nonce, and return the second refusal.

    Args:
        module: the MuSig2 module, this package's or zkp's.

    Returns:
        The refusal, and the secret nonces of the session.
    """
    cache, secnonces, session = two_of_two_session(module)
    memories: list[str | bytes] = [nonce_memory(secnonce) for secnonce in secnonces]
    assert all(any(memory) for memory in memories)
    secnonces[0].partial_sign(SECRET, cache, session)
    with pytest.raises(ValueError, match="already spent") as caught:
        secnonces[0].partial_sign(SECRET, cache, session)
    return caught.value, memories


def mismatched_nonce(
    module: types.ModuleType = musig, context_check: Callable[[], None] = check
) -> tuple[BaseException, list[str | bytes]]:
    """Sign with the second signer's key and the first signer's nonce.

    Args:
        module: the MuSig2 module, this package's or zkp's.
        context_check: the `check` of that module's context.

    Returns:
        The refusal, and the secret nonces of the session.
    """
    cache, secnonces, session = two_of_two_session(module)
    memories: list[str | bytes] = [nonce_memory(secnonce) for secnonce in secnonces]
    assert all(any(memory) for memory in memories)
    with pytest.raises(ValueError, match="private key does not match") as caught:
        secnonces[0].partial_sign(OTHER, cache, session)
    context_check()  # silent: the key is refused before libsecp256k1 is asked
    return caught.value, memories


def refused_in_public_position(
    call: Callable[[bytes], object],
    phrases: tuple[str, ...],
    value: bytes,
    in_play: list[str | bytes],
) -> None:
    """Feed the secret, cut to a public type, and read the refusal.

    Args:
        call: the call, with the value in the public position.
        phrases: the wordings the source gives that refusal; one of them
            has to be in it.
        value: the secret, cut to the public type.
        in_play: the other secrets the call may hold.
    """
    with pytest.raises((TypeError, ValueError, RuntimeError)) as caught:
        call(value)
    assert any(phrase in str(caught.value) for phrase in phrases)
    assert_free(caught.value, [*spellings(value), *in_play])


def wiped_signer() -> BaseException:
    """Sign with a signer that has been wiped.

    Returns:
        The refusal.
    """
    signer = ssa.Signer(SECRET)
    signer.wipe()
    with pytest.raises(ValueError, match="wiped") as caught:
        signer.sign(MSG)
    return caught.value


#: Each entry point that takes a private key or a tweak of one, by the
#: position the secret is fed in, with what a refusal calls it.
SCALARS: dict[str, tuple[str, Callable[[Any], object]]] = {
    "keys.prvkey_verify": ("the private key must", keys.prvkey_verify),
    "keys.prvkey_negate": ("the private key must", keys.prvkey_negate),
    "keys.prvkey_tweak_add prvkey": (
        "the private key must",
        lambda v: keys.prvkey_tweak_add(v, TWEAK),
    ),
    "keys.prvkey_tweak_add tweak": (
        "the tweak must",
        lambda v: keys.prvkey_tweak_add(OTHER, v),
    ),
    "keys.prvkey_tweak_mul prvkey": (
        "the private key must",
        lambda v: keys.prvkey_tweak_mul(v, TWEAK),
    ),
    "keys.prvkey_tweak_mul tweak": (
        "the tweak must",
        lambda v: keys.prvkey_tweak_mul(OTHER, v),
    ),
    "keys.pubkey_from_prvkey": ("the private key must", keys.pubkey_from_prvkey),
    "keys.pubkey_tweak_add": (
        "the tweak must",
        lambda v: keys.pubkey_tweak_add(PUB, v),
    ),
    "keys.pubkey_tweak_mul": (
        "the tweak must",
        lambda v: keys.pubkey_tweak_mul(PUB, v),
    ),
    "keys.pubkey_tweak_mul_sum": (
        "the tweak must",
        lambda v: keys.pubkey_tweak_mul_sum([PUB], [v]),
    ),
    "keys.PubkeyTweakChain.tweak_add": (
        "the tweak must",
        lambda v: keys.PubkeyTweakChain(PUB).tweak_add(v),
    ),
    "xonly.from_prvkey": ("the private key must", xonly.from_prvkey),
    "xonly.from_keypair": ("struct secp256k1_keypair", xonly.from_keypair),
    "xonly.tweak_add": ("the tweak must", lambda v: xonly.tweak_add(XONLY, v)),
    "xonly.tweak_add_check": (
        "the tweak must",
        lambda v: xonly.tweak_add_check(XONLY, 0, XONLY, v),
    ),
    "xonly.prvkey_tweak_add prvkey": (
        "the private key must",
        lambda v: xonly.prvkey_tweak_add(v, TWEAK),
    ),
    "xonly.prvkey_tweak_add tweak": (
        "the tweak must",
        lambda v: xonly.prvkey_tweak_add(OTHER, v),
    ),
    "dsa.nonce_rfc6979": ("the private key must", lambda v: dsa.nonce_rfc6979(MSG, v)),
    "dsa.sign": ("the private key must", lambda v: dsa.sign(MSG, v)),
    "recovery.sign": ("the private key must", lambda v: recovery.sign(MSG, v)),
    "ssa.nonce_bip340": ("the private key must", lambda v: ssa.nonce_bip340(MSG, v)),
    "ssa.sign": ("the private key must", lambda v: ssa.sign(MSG, v)),
    "ssa.sign_custom": ("the private key must", lambda v: ssa.sign_custom(MSG, v)),
    "ssa.Signer": ("the private key must", ssa.Signer),
    "ecdh.shared_secret": (
        "the private key must",
        lambda v: ecdh.shared_secret(PUB, v),
    ),
    "ecdh.shared_point": ("the private key must", lambda v: ecdh.shared_point(PUB, v)),
    "ellswift.create": ("the private key must", ellswift.create),
    "ellswift.xdh": (
        "the private key must",
        lambda v: ellswift.xdh(ELL_A, ELL_B, v, 0),
    ),
    "musig.nonce_gen": ("the private key must", lambda v: musig.nonce_gen(PUB, v)),
    "musig.nonce_gen_counter": (
        "the private key must",
        lambda v: musig.nonce_gen_counter(v, 1),
    ),
    "musig.SecretNonce.partial_sign": ("the private key must", partial_sign_with),
    "musig.KeyAggCache.pubkey_ec_tweak_add": (
        "the tweak must",
        lambda v: musig.KeyAggCache([PUB]).pubkey_ec_tweak_add(v),
    ),
    "musig.KeyAggCache.pubkey_xonly_tweak_add": (
        "the tweak must",
        lambda v: musig.KeyAggCache([PUB]).pubkey_xonly_tweak_add(v),
    ),
    "silentpayments.create_outputs prvkeys": (
        "the private key must",
        lambda v: silentpayments.create_outputs([(PUB, PUB)], bytes(36), prvkeys=[v]),
    ),
    "silentpayments.create_outputs taproot_prvkeys": (
        "the private key must",
        lambda v: silentpayments.create_outputs(
            [(PUB, PUB)], bytes(36), taproot_prvkeys=[v]
        ),
    ),
    "silentpayments.scan_outputs labels": (
        "the label tweak must",
        lambda v: silentpayments.scan_outputs(
            [XONLY],
            OTHER,
            silentpayments.prevouts_summary(bytes(36), pubkeys_bytes=[PUB]),
            PUB,
            {LABEL: v},
        ),
    ),
    "silentpayments.label": (
        "the scan private key must",
        lambda v: silentpayments.label(v, 0),
    ),
    "silentpayments.scan_outputs scan_prvkey": (
        "the scan private key must",
        lambda v: silentpayments.scan_outputs(
            [XONLY],
            v,
            silentpayments.prevouts_summary(bytes(36), pubkeys_bytes=[PUB]),
            PUB,
        ),
    ),
}

#: The pairs that are no refusal: `prvkey_verify` answers a verdict for a
#: value of the wrong size or range, `tweak_add_check` for a tweak at the
#: order, and a scan with a label tweak at the order finds nothing.
VERDICTS = {
    ("keys.prvkey_verify", wrong)
    for wrong in (
        "short",
        "long",
        "long bytearray",
        "long cdata",
        "big int",
        "negative int",
        "at the order",
    )
} | {
    ("xonly.tweak_add_check", "at the order"),
    ("silentpayments.scan_outputs labels", "at the order"),
}

#: What the refusal of a key or a tweak at the order says, by entry point. A
#: few say nothing of the argument: they are this package's message for a
#: call libsecp256k1 failed.
KEY = "invalid private key: not in [1, n-1]"
TWEAKED = "invalid tweak or resulting public key"
ORDER = {
    "keys.prvkey_negate": KEY,
    "keys.prvkey_tweak_add prvkey": "invalid private key or tweak",
    "keys.prvkey_tweak_add tweak": "invalid private key or tweak",
    "keys.prvkey_tweak_mul prvkey": "invalid private key or tweak",
    "keys.prvkey_tweak_mul tweak": "invalid private key or tweak",
    "keys.pubkey_from_prvkey": KEY,
    "keys.pubkey_tweak_add": TWEAKED,
    "keys.pubkey_tweak_mul": "invalid tweak",
    "keys.pubkey_tweak_mul_sum": "invalid tweak",
    "keys.PubkeyTweakChain.tweak_add": TWEAKED,
    "xonly.from_prvkey": KEY,
    "xonly.from_keypair": "struct secp256k1_keypair",
    "xonly.tweak_add": TWEAKED,
    "xonly.prvkey_tweak_add prvkey": KEY,
    "xonly.prvkey_tweak_add tweak": "invalid tweak or resulting private key",
    "dsa.nonce_rfc6979": KEY,
    "dsa.sign": KEY,
    "recovery.sign": KEY,
    "ssa.nonce_bip340": KEY,
    "ssa.sign": KEY,
    "ssa.sign_custom": KEY,
    "ssa.Signer": KEY,
    "ecdh.shared_secret": "invalid private key",  # pragma: allowlist secret
    "ecdh.shared_point": "invalid private key",
    "ellswift.create": KEY,
    "ellswift.xdh": "invalid private key",
    "musig.nonce_gen": KEY,
    "musig.nonce_gen_counter": KEY,
    "musig.SecretNonce.partial_sign": KEY,
    "musig.KeyAggCache.pubkey_ec_tweak_add": TWEAKED,
    "musig.KeyAggCache.pubkey_xonly_tweak_add": TWEAKED,
    "silentpayments.create_outputs prvkeys": "silent payment output creation failed",
    "silentpayments.create_outputs taproot_prvkeys": KEY,
    "silentpayments.label": "invalid scan private key",
    "silentpayments.scan_outputs scan_prvkey": "silent payment scanning failed",
}

#: The pairs where the secret, cut to the size of a public type, is one: any
#: 32 octets below the order are a partial signature, any 64 whose two
#: halves are below the order are a compact signature, and any 64 are an
#: ElligatorSwift key.
PARSES = {
    ("dsa.parse_compact", "64 bytes"),
    ("ellswift.decode", "64 bytes"),
    ("ellswift.xdh", "64 bytes"),
    ("musig.partial_sig_parse", "32 bytes"),
}

#: Each entry point that takes a nonce or the entropy of one, by the
#: position the secret is fed in, with what a refusal calls it.
ENTROPIES: dict[str, tuple[str, Callable[[Any], object]]] = {
    "dsa.nonce_rfc6979": (
        "the aux_rand32 must",
        lambda v: dsa.nonce_rfc6979(MSG, OTHER, v),
    ),
    "dsa.sign": ("the aux_rand32 must", lambda v: dsa.sign(MSG, OTHER, v)),
    "recovery.sign": ("the aux_rand32 must", lambda v: recovery.sign(MSG, OTHER, v)),
    "ssa.nonce_bip340": (
        "the aux_rand32 must",
        lambda v: ssa.nonce_bip340(MSG, OTHER, v),
    ),
    "ssa.sign": ("the aux_rand32 must", lambda v: ssa.sign(MSG, OTHER, v)),
    "ssa.sign_custom": (
        "the aux_rand32 must",
        lambda v: ssa.sign_custom(MSG, OTHER, v),
    ),
    "ssa.Signer.sign": (
        "the aux_rand32 must",
        lambda v: ssa.Signer(OTHER).sign(MSG, v),
    ),
    "ssa.Signer.sign_custom": (
        "the aux_rand32 must",
        lambda v: ssa.Signer(OTHER).sign_custom(MSG, v),
    ),
    "ellswift.create": ("the aux_rand32 must", lambda v: ellswift.create(OTHER, v)),
    "ellswift.encode": ("the aux_rand32 must", lambda v: ellswift.encode(PUB, v)),
    "musig.nonce_gen": (
        "the extra_input32 must",
        lambda v: musig.nonce_gen(PUB, OTHER, extra_input32=v),
    ),
    "musig.nonce_gen_counter": (
        "the extra_input32 must",
        lambda v: musig.nonce_gen_counter(OTHER, 1, extra_input32=v),
    ),
}

#: Each entry point that takes a native secret nonce, by the position the
#: secret is fed in. The refusal is cffi's, so its wording is not checked.
SECNONCES: dict[str, Callable[[Any], object]] = {
    "musig.SecretNonce": secret_nonce_with,
}

#: Each parameter that takes a list or a mapping of secrets, with the secret
#: fed bare in its place, at a length the call refuses. A bare value is
#: refused for its type or its length, so the wording is not checked. At a
#: matching length `pubkey_tweak_mul_sum` takes it as a list of one-byte
#: tweaks (btclib-org/btclib-secp256k1#1229). `create_outputs`' `prvkeys`
#: and `taproot_prvkeys` take it so at any length
#: (btclib-org/btclib-secp256k1#1228), so they are not here.
BARE: dict[str, Callable[[Any], object]] = {
    "silentpayments.scan_outputs labels": lambda v: silentpayments.scan_outputs(
        [XONLY],
        OTHER,
        silentpayments.prevouts_summary(bytes(36), pubkeys_bytes=[PUB]),
        PUB,
        v,
    ),
    "keys.pubkey_tweak_mul_sum tweaks": lambda v: keys.pubkey_tweak_mul_sum([PUB], v),
}

#: Each refusal that a good secret reaches: the call, and the secrets it
#: computes, which `IN_PLAY` does not hold.
VALID_SECRETS: dict[str, tuple[Callable[[], object], list[str | bytes]]] = {
    "keys.prvkey_tweak_add to zero": (
        prvkey_tweak_add_cancelling,
        [(N - SECRET_INT).to_bytes(32, "big")],
    ),
    "keys.prvkey_tweak_mul by zero": (
        lambda: keys.prvkey_tweak_mul(SECRET, bytes(32)),
        [],
    ),
    "xonly.prvkey_tweak_add to zero": (
        xonly_prvkey_tweak_add_cancelling,
        [(N - SECRET_INT).to_bytes(32, "big")],
    ),
    "dsa.sign for another public key": (
        lambda: dsa.sign(MSG, SECRET, pubkey=PUB),
        [],
    ),
    "dsa.sign without verify but with a public key": (
        lambda: dsa.sign(MSG, SECRET, pubkey=SECRET_PUB, verify=False),
        [],
    ),
    "dsa.sign with entropy and grinding": (
        lambda: dsa.sign(MSG, SECRET, AUX, grind=True),
        [],
    ),
    "recovery.sign for another public key": (
        lambda: recovery.sign(MSG, SECRET, pubkey=PUB),
        [],
    ),
    "recovery.sign without verify but with a public key": (
        lambda: recovery.sign(MSG, SECRET, pubkey=SECRET_PUB, verify=False),
        [],
    ),
    "ecdh.shared_secret into a buffer the secret is": (
        lambda: ecdh.shared_secret(PUB, OTHER, into=SECRET),  # type: ignore[call-overload]
        [ecdh.shared_secret(PUB, OTHER)],
    ),
    "keys.prvkey_negate into a buffer the secret is": (
        lambda: keys.prvkey_negate(OTHER, into=SECRET),  # type: ignore[call-overload]
        [keys.prvkey_negate(OTHER)],
    ),
    "silentpayments.label past the label range": (
        lambda: silentpayments.label(SECRET, 2**32),
        [],
    ),
}

#: Each public type refused with the secret in its place: the call, and
#: what a refusal calls the position.
PUBLIC_POSITIONS: dict[str, tuple[Callable[[bytes], object], tuple[str, ...]]] = {
    "keys.parse": (keys.parse, ("invalid public key",)),
    "keys.pubkey_tweak_add": (
        lambda v: keys.pubkey_tweak_add(v, TWEAK),
        ("invalid public key",),
    ),
    "keys.pubkey_negate": (keys.pubkey_negate, ("invalid public key",)),
    "keys.pubkey_combine": (
        lambda v: keys.pubkey_combine([PUB, v]),
        ("invalid public key",),
    ),
    "keys.reserialize": (keys.reserialize, ("invalid public key",)),
    "xonly.parse": (xonly.parse, ("invalid public key",)),
    "xonly.tweak_add": (lambda v: xonly.tweak_add(v, TWEAK), ("invalid public key",)),
    "dsa.parse_der": (dsa.parse_der, ("invalid DER signature",)),
    "dsa.parse_compact": (dsa.parse_compact, ("invalid compact signature",)),
    "ecdh.shared_secret": (
        lambda v: ecdh.shared_secret(v, OTHER),
        ("invalid public key",),
    ),
    "ellswift.decode": (ellswift.decode, ("the ElligatorSwift public key must",)),
    "ellswift.encode": (ellswift.encode, ("invalid public key",)),
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
    "ellswift.xdh": (
        lambda v: ellswift.xdh(v, ELL_B, OTHER, 0),
        ("the ElligatorSwift public key of A must",),
    ),
    "musig.KeyAggCache": (
        lambda v: musig.KeyAggCache([v]),
        ("invalid public key at index 0",),
    ),
    "silentpayments.parse_label": (
        silentpayments.parse_label,
        ("invalid label", "the label must"),
    ),
}

#: What a secret is made into to be taken for each public type: the right
#: length and, where the type has a prefix byte, one no encoding defines,
#: as a mistaken argument would be.
SHAPES = {
    "33 bytes": b"\x05" + SECRET,
    "65 bytes": b"\x05" + SECRET + SECRET,
    "64 bytes": SECRET + SECRET,
    "66 bytes": b"\x05" + SECRET + b"\x05" + SECRET,
    "32 bytes": SECRET,
}
assert all(len(value) == int(name.split()[0]) for name, value in SHAPES.items())


def test_every_entry_point_that_takes_a_secret_is_fed_one() -> None:
    """Read the parameters of the public API, and find each in a table."""
    found = secret_entry_points(package_modules(btclib_secp256k1))
    assert found["dsa.sign"] == (["prvkey"], ["aux_rand32"])
    assert untested(found, SCALARS, {**ENTROPIES, **SECNONCES}) == []
    # each parameter needs its entry, not only the entry point
    two: dict[str, tuple[list[str], list[str]]] = {
        "keys.prvkey_tweak_add": (["prvkey", "tweak"], [])
    }
    assert untested(two, {"keys.prvkey_tweak_add prvkey": None}, {}) == [
        "keys.prvkey_tweak_add tweak"
    ]
    one: dict[str, tuple[list[str], list[str]]] = {
        "keys.nothing": (["prvkey"], ["nonce"])
    }
    assert untested(one, SCALARS, ENTROPIES) == [
        "keys.nothing prvkey",
        "keys.nothing nonce",
    ]


@pytest.mark.parametrize(
    "entry,wrong",
    [
        (entry, wrong)
        for entry in SCALARS
        for wrong in WRONG_SCALAR
        if (entry, wrong) not in VERDICTS
    ],
)
def test_a_wrong_private_key_is_refused_without_quoting_it(
    entry: str, wrong: str
) -> None:
    """Feed the secret as the wrong private key or tweak, and read the refusal.

    Args:
        entry: the entry point, by name.
        wrong: the way the secret is wrong, by name.
    """
    label, call = SCALARS[entry]
    value = WRONG_SCALAR[wrong]
    phrase = ORDER[entry] if wrong == "at the order" else label
    DRAWN.clear()
    exc = refused(lambda: call(value), (phrase,))
    assert_free(exc, [*spellings(value), *IN_PLAY, *DRAWN])


@pytest.mark.parametrize("wrong", WRONG_ENTROPY)
@pytest.mark.parametrize("entry", ENTROPIES)
def test_a_wrong_nonce_is_refused_without_quoting_it(entry: str, wrong: str) -> None:
    """Feed the secret as the wrong nonce entropy, and read the refusal.

    Args:
        entry: the entry point, by name.
        wrong: the way the secret is wrong, by name.
    """
    label, call = ENTROPIES[entry]
    value = WRONG_ENTROPY[wrong]
    exc = refused(lambda: call(value), (label,))
    assert_free(exc, [*spellings(value), *IN_PLAY])


def refused_anyhow(call: Callable[[], object]) -> BaseException:
    """Return the refusal a call ends in, whatever it says.

    Args:
        call: the call, with the secret in the position under test.

    Returns:
        The exception raised.
    """
    with pytest.raises((TypeError, ValueError, RuntimeError)) as caught:
        call()
    return caught.value


@pytest.mark.parametrize("wrong", WRONG)
@pytest.mark.parametrize("entry", SECNONCES)
def test_a_wrong_secret_nonce_is_refused_without_quoting_it(
    entry: str, wrong: str
) -> None:
    """Feed the secret as the native secret nonce, and read the refusal.

    Args:
        entry: the entry point, by name.
        wrong: the way the secret is wrong, by name.
    """
    value = own_copy(WRONG[wrong])
    DRAWN.clear()
    exc = refused_anyhow(lambda: SECNONCES[entry](value))
    assert_free(exc, [*spellings(WRONG[wrong]), *IN_PLAY, *DRAWN])


@pytest.mark.parametrize("wrong", WRONG_SCALAR)
@pytest.mark.parametrize("entry", BARE)
def test_a_secret_passed_bare_for_a_container_is_not_quoted(
    entry: str, wrong: str
) -> None:
    """Feed the secret where a list or a mapping of them belongs.

    Args:
        entry: the entry point and parameter, by name.
        wrong: the way the secret is wrong, by name.
    """
    value = WRONG_SCALAR[wrong]
    exc = refused_anyhow(lambda: BARE[entry](value))
    assert_free(exc, [*spellings(value), *IN_PLAY])


@pytest.mark.parametrize("case", VALID_SECRETS)
def test_a_refusal_a_good_secret_reaches_does_not_quote_it(case: str) -> None:
    """Refuse a call whose secret is a good one, and read the refusal.

    Args:
        case: the refusal, by name.
    """
    call, secrets = VALID_SECRETS[case]
    with pytest.raises((TypeError, ValueError, RuntimeError)) as caught:
        call()
    assert_free(caught.value, [*secrets, *IN_PLAY])


def test_a_signer_wiped_does_not_quote_the_key() -> None:
    """Sign with a wiped signer, and read the refusal."""
    assert_free(wiped_signer(), IN_PLAY)


@pytest.mark.parametrize("case", [spent_nonce, mismatched_nonce])
def test_a_secret_nonce_refused_does_not_quote_the_nonce_or_the_key(
    case: Callable[[], tuple[BaseException, list[str | bytes]]],
) -> None:
    """Refuse a signature with a spent nonce or the wrong key, and read it.

    Args:
        case: the way the signature is refused.
    """
    exc, secrets = case()
    assert_free(exc, [*secrets, *IN_PLAY])


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
    """Feed the secret in a public position, and read the refusal.

    Args:
        entry: the entry point, by name.
        shape: how the secret is cut to the public type, by name.
    """
    call, phrases = PUBLIC_POSITIONS[entry]
    refused_in_public_position(call, phrases, SHAPES[shape], IN_PLAY)
