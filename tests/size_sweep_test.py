# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""A wrong size is refused at every sized call site of the mainline modules.

libsecp256k1 reads a fixed number of octets from a bare pointer, so the
length check in front of each call is what keeps a short argument from
being read past its end. A test that names the entry points it hands a
wrong size to says nothing about the ones it does not, so this one
takes both halves of the question from the modules themselves:

- *where the checks are*: every call in a mainline module to
  `_scalar.octets` with a size, `_scalar.scalar`, `_scalar.entropy` or
  `_scalar.optional_entropy` is read off the module's source;
- *what reaches them*: the entry points of `tests/bytes_like_test.py`'s
  table and of the `musig` table below are driven with each bytes
  argument replaced by a shorter and a longer one, and with each
  replaced by an int outside a scalar's range, while the four functions
  above are wrapped to record what each call site was handed and what it
  did.

A site that is not handed a wrong size on a side, or that accepts one,
fails here. So does a bytes argument that takes a wrong length without
being named in `UNSIZED`, which is how a check dropped from a site shows
up: the source no longer lists the site, but the argument is accepted.

The `zkp` subpackage is not swept: it exists only in a build made with
`BTCLIB_LIBSECP256K1_ZKP`, and its tests are skipped in any other.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
import re
import sys
from collections import defaultdict
from collections.abc import Callable, Iterator
from types import ModuleType
from typing import Any

import pytest

import btclib_secp256k1
from btclib_secp256k1 import _scalar, keys, musig
from tests.bytes_like_test import CALLS, TWEAK, at_the_boundary

Call = tuple[str, Callable[..., Any], tuple[Any, ...], dict[str, Any]]

MSG = b"\x01" * 32
PRVKEYS = [(1).to_bytes(32, "big"), (2).to_bytes(32, "big")]
PUBKEYS = [keys.pubkey_from_prvkey(prvkey) for prvkey in PRVKEYS]
XONLY_TWEAK = (3).to_bytes(32, "big")

CACHE = musig.KeyAggCache(PUBKEYS)


def round_one() -> list[musig.SecretNonce]:
    """Generate one secret nonce per signer, for the cache above.

    Returns:
        The secret nonces, in `PRVKEYS` order.
    """
    return [
        musig.nonce_gen(pubkey, prvkey, msg32=MSG, keyagg_cache=CACHE)
        for prvkey, pubkey in zip(PRVKEYS, PUBKEYS, strict=True)
    ]


NONCES = round_one()
PUBNONCES = [nonce.pubnonce for nonce in NONCES]
AGGNONCE = musig.nonce_agg(PUBNONCES)
SESSION = musig.Session(AGGNONCE, MSG, CACHE)
PARTIAL_SIGS = []
for _nonce, _prvkey in zip(NONCES, PRVKEYS, strict=True):
    PARTIAL_SIGS.append(_nonce.partial_sign(_prvkey, CACHE, SESSION))


def key_aggregated(pubkeys: list[bytes]) -> bytes:
    """Aggregate public keys.

    Args:
        pubkeys: the public keys.

    Returns:
        The x-only aggregate.
    """
    return musig.KeyAggCache(pubkeys).agg_pubkey


def ec_tweaked(tweak: bytes) -> bytes:
    """Add an EC tweak to a fresh key aggregation.

    Args:
        tweak: the tweak.

    Returns:
        The tweaked aggregate public key.
    """
    return musig.KeyAggCache(PUBKEYS).pubkey_ec_tweak_add(tweak)


def xonly_tweaked(tweak: bytes) -> bytes:
    """Add an x-only tweak to a fresh key aggregation.

    Args:
        tweak: the tweak.

    Returns:
        The tweaked aggregate public key.
    """
    return musig.KeyAggCache(PUBKEYS).pubkey_xonly_tweak_add(tweak)


def generated(
    pubkey: bytes, prvkey: bytes, msg32: bytes, extra_input32: bytes
) -> bytes:
    """Generate a secret nonce with randomness, and answer its public half.

    Args:
        pubkey: the signer's public key.
        prvkey: the signer's private key.
        msg32: the message hash.
        extra_input32: extra input.

    Returns:
        The public nonce.
    """
    with musig.nonce_gen(
        pubkey, prvkey, msg32, CACHE, extra_input32=extra_input32
    ) as nonce:
        return nonce.pubnonce


def generated_by_counter(prvkey: bytes, msg32: bytes, extra_input32: bytes) -> bytes:
    """Generate a secret nonce from a counter, and answer its public half.

    Args:
        prvkey: the signer's private key.
        msg32: the message hash.
        extra_input32: extra input.

    Returns:
        The public nonce.
    """
    with musig.nonce_gen_counter(
        prvkey, 1, msg32, CACHE, extra_input32=extra_input32
    ) as nonce:
        return nonce.pubnonce


def in_session(aggnonce: bytes, msg32: bytes) -> bool:
    """Start a session on the cache above.

    Args:
        aggnonce: the aggregate nonce.
        msg32: the message hash.

    Returns:
        True, the session being thrown away.
    """
    musig.Session(aggnonce, msg32, CACHE)
    return True


def signed_partially(prvkey: bytes) -> bytes:
    """Sign a session of its own with a secret nonce of its own.

    Args:
        prvkey: the private key of the first signer.

    Returns:
        The partial signature.
    """
    with round_one()[0] as nonce:
        return nonce.partial_sign(prvkey, CACHE, SESSION)


MUSIG_CALLS: list[Call] = [
    ("musig.pubnonce_parse", musig.pubnonce_parse, (PUBNONCES[0],), {}),
    ("musig.aggnonce_parse", musig.aggnonce_parse, (AGGNONCE,), {}),
    ("musig.partial_sig_parse", musig.partial_sig_parse, (PARTIAL_SIGS[0],), {}),
    ("musig.nonce_agg", musig.nonce_agg, (PUBNONCES,), {}),
    ("musig.KeyAggCache", key_aggregated, (PUBKEYS,), {}),
    ("musig.KeyAggCache.pubkey_ec_tweak_add", ec_tweaked, (TWEAK,), {}),
    ("musig.KeyAggCache.pubkey_xonly_tweak_add", xonly_tweaked, (TWEAK,), {}),
    ("musig.nonce_gen", generated, (PUBKEYS[0], PRVKEYS[0], MSG, MSG), {}),
    ("musig.nonce_gen_counter", generated_by_counter, (PRVKEYS[0], MSG, MSG), {}),
    ("musig.Session", in_session, (AGGNONCE, MSG), {}),
    (
        "musig.Session.partial_sig_verify",
        SESSION.partial_sig_verify,
        (PARTIAL_SIGS[0], PUBNONCES[0], PUBKEYS[0], CACHE),
        {},
    ),
    ("musig.Session.partial_sig_agg", SESSION.partial_sig_agg, (PARTIAL_SIGS,), {}),
    ("musig.SecretNonce.partial_sign", signed_partially, (PRVKEYS[0],), {}),
]

# the musig module's own entry points the table above does not name: the
# serializers, `_cache_`, `_session_`, `pubkey_get` and `wipe` take an
# object or nothing and no bytes, and the classes are driven through
# their methods
MUSIG_NOT_SWEPT = {
    "musig.aggnonce_serialize",
    "musig.partial_sig_serialize",
    "musig.pubnonce_serialize",
    "musig.KeyAggCache._cache_",
    "musig.KeyAggCache.pubkey_get",
    "musig.SecretNonce.wipe",
    "musig.SecretNonce",
    "musig.Session._session_",
}

SWEPT = [*CALLS, *MUSIG_CALLS]

# bytes arguments of the table that take a length other than the one they
# are given, as (entry, which bytes in the order of its arguments, a
# sequence or a mapping counting each item). Everything else must refuse
UNSIZED = {
    # any length of tag and of message
    ("hashes.tagged_sha256", 0),
    ("hashes.tagged_sha256", 1),
    # BIP340 signs a message of any length, not only a hash, and derives
    # its nonce from one
    ("ssa.sign_custom", 0),
    ("ssa.Signer.sign_custom", 1),
    ("ssa.nonce_bip340", 0),
}

# sized sites no wrong size can reach, as (module, function, check): an
# earlier check of the same argument refuses first
GUARDED = {
    # `xonly.from_prvkey` has checked the private key by then
    ("btclib_secp256k1.ssa", "nonce_bip340", "scalar"),
}

REAL: dict[str, Callable[..., Any]] = {
    "octets": _scalar.octets,
    "scalar": _scalar.scalar,
    "entropy": _scalar.entropy,
    "optional_entropy": _scalar.optional_entropy,
}

# an int too large for a scalar, and one below zero
OUT_OF_RANGE = (2**256, 2**256 + 1, 2**512, -1)


def mainline() -> list[ModuleType]:
    """Return the modules of the package, the subpackage left out.

    Returns:
        Every module directly under `btclib_secp256k1`, read from the
        package's own path, `_scalar` aside: it is what is swept.
    """
    return [
        importlib.import_module(f"btclib_secp256k1.{info.name}")
        for info in pkgutil.iter_modules(btclib_secp256k1.__path__)
        if not info.ispkg and info.name != "_scalar"
    ]


def bound_names(module: ModuleType) -> dict[str, str]:
    """Return the names a module binds the four checks to.

    Args:
        module: the module.

    Returns:
        Each name in the module that is one of the four functions, with
        the function's own name.
    """
    return {
        name: real_name
        for name, value in vars(module).items()
        for real_name, real in REAL.items()
        if value is real
    }


def sized_sites(module: ModuleType) -> list[tuple[int, int, str, str]]:
    """Return the calls in a module that check a length.

    Args:
        module: the module, read from its source.

    Returns:
        The first line, the last line, the enclosing function and the
        check of each call to `octets` with a size, or to any of the
        other three.
    """
    names = bound_names(module)
    tree = ast.parse(inspect.getsource(module))
    # `ast.walk` meets an outer function before one inside it, so the
    # innermost function is the one left standing
    owner: dict[int, str] = {}
    for scope in ast.walk(tree):
        if isinstance(scope, ast.FunctionDef):
            owner |= {id(node): scope.name for node in ast.walk(scope)}
    sites = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in names
        ):
            continue
        real_name = names[node.func.id]
        sizes = [kw.value for kw in node.keywords if kw.arg == "size"]
        sizes += node.args[2:3]
        if real_name == "octets" and all(
            isinstance(size, ast.Constant) and size.value is None for size in sizes
        ):
            continue
        assert node.end_lineno is not None
        sites.append((node.lineno, node.end_lineno, owner[id(node)], real_name))
    return sites


# what each site was handed and what it did, by (module, line): the
# side of the size, and whether the call refused it
SEEN: dict[tuple[str, int], dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))


def side(real_name: str, value: Any, size: int) -> str | None:
    """Say which way an argument is wrong for a check, if it is.

    Args:
        real_name: which check.
        value: what the call site passed.
        size: the length the check demands.

    Returns:
        "short", "long" or "past" (an int outside a scalar's range), or
        None where the argument is right or is something else.
    """
    if real_name == "scalar" and type(value) is int:
        return "past" if not 0 <= value < 2**256 else None
    if not isinstance(value, bytes) or len(value) == size:
        return None
    return "short" if len(value) < size else "long"


def recorded(real_name: str) -> Callable[..., Any]:
    """Wrap a check so that it records what its caller handed it.

    Args:
        real_name: which check.

    Returns:
        A function answering what the check answers, and raising what it
        raises, noting first the calling line and then what came of it.
    """
    real = REAL[real_name]

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        caller = sys._getframe(1)
        key = (caller.f_globals["__name__"], caller.f_lineno)
        size: int | None = 32
        if real_name == "octets":
            size = args[2] if len(args) > 2 else kwargs.get("size")
        wrong = None if size is None else side(real_name, args[0], size)
        outcome = "accepted"
        try:
            return real(*args, **kwargs)
        except ValueError:
            outcome = "refused"
            raise
        finally:
            if wrong is not None:
                SEEN[key][wrong].add(outcome)

    return wrapper


def leaves(value: Any) -> list[bytes]:
    """Return the bytes inside an argument, in order.

    A sequence is walked, and a mapping is walked key then value.

    Args:
        value: one argument.

    Returns:
        The bytes, each of them one place a wrong size can be put.
    """
    if isinstance(value, bytes):
        return [value]
    if isinstance(value, (list, tuple)):
        return [leaf for item in value for leaf in leaves(item)]
    if isinstance(value, dict):
        return [leaf for item in value.items() for leaf in leaves(item)]
    return []


def rebuilt(value: Any, fresh: Iterator[Any]) -> Any:
    """Return an argument with each of its bytes replaced by the next.

    Args:
        value: one argument.
        fresh: what to put in the places `leaves` lists, in its order.

    Returns:
        The argument, of the same shape.
    """
    if isinstance(value, bytes):
        return next(fresh)
    if isinstance(value, (list, tuple)):
        return type(value)(rebuilt(item, fresh) for item in value)
    if isinstance(value, dict):
        return dict(rebuilt(list(value.items()), fresh))
    return value


def variants(leaf: bytes) -> list[Any]:
    """Return the wrong arguments to put where a leaf is.

    Args:
        leaf: the right argument.

    Returns:
        Empty, one short, one long, twice as long, a megabyte, and the
        ints no scalar is.
    """
    return [
        b"",
        leaf[:-1],
        leaf + b"\x00",
        leaf * 2,
        bytes(10**6),
        *OUT_OF_RANGE,
    ]


def refused(call: Callable[..., Any], args: tuple[Any, ...], kwargs: Any) -> bool:
    """Say whether a call refuses its arguments.

    A refusal is a `ValueError` or a `TypeError`, or the `False` a
    verdict function answers.

    Args:
        call: the entry point.
        args: its arguments.
        kwargs: its keyword arguments.

    Returns:
        True if it refused.
    """
    try:
        return call(*args, **kwargs) is False
    except (ValueError, TypeError):
        return True


def sweep() -> set[tuple[str, int]]:
    """Drive every entry point of the table with every wrong argument.

    Returns:
        The (entry, which bytes of its arguments) that accepted a wrong
        length, a wrong int excepted.
    """
    accepted = set()
    for name, call, args, kwargs in SWEPT:
        places = leaves(args)
        for index, leaf in enumerate(places):
            for wrong in variants(leaf):
                changed = [*places[:index], wrong, *places[index + 1 :]]
                if not refused(call, rebuilt(args, iter(changed)), kwargs):
                    accepted.add((name, index))
    return accepted


@pytest.fixture(scope="module")
def swept() -> set[tuple[str, int]]:
    """Run the sweep with the checks recording, and put them back.

    Returns:
        What `sweep` answers.
    """
    SEEN.clear()
    with pytest.MonkeyPatch.context() as patch:
        for module in mainline():
            for name, real_name in bound_names(module).items():
                patch.setattr(module, name, recorded(real_name))
        return sweep()


def test_every_bytes_argument_but_the_named_is_sized(
    swept: set[tuple[str, int]],
) -> None:
    """A wrong length is refused wherever the table does not excuse it.

    The set must be what is named, both ways: an argument taking a wrong
    length without being named is a check missing, and one named
    that refuses is an excuse that no longer excuses anything.

    Args:
        swept: the arguments that accepted a wrong length.
    """
    assert swept == UNSIZED, sorted(swept ^ UNSIZED)


def test_every_sized_site_is_refused_both_sides(swept: set[tuple[str, int]]) -> None:
    """Every call site that checks a length was handed and refused each side.

    A scalar was also handed an int outside its range. The sites are read
    from the modules' source, so one added anywhere in them is listed
    here, and fails until something drives it.

    Args:
        swept: the sweep having run, which fills `SEEN`.
    """
    assert swept
    wrong = []
    for module in mainline():
        for first, last, function, real_name in sized_sites(module):
            seen: dict[str, set[str]] = defaultdict(set)
            for (name, line), events in SEEN.items():
                if name == module.__name__ and first <= line <= last:
                    for event, outcomes in events.items():
                        seen[event] |= outcomes
            required = {"short", "long"} | (
                {"past"} if real_name == "scalar" else set()
            )
            where = f"{module.__name__}:{first} in {function}, {real_name}"
            if (module.__name__, function, real_name) in GUARDED:
                wrong += [
                    f"{where}: {event} is reached, so it is not guarded"
                    for event in seen
                ]
                continue
            wrong += [
                f"{where}: {event} {sorted(seen[event])}"
                for event in sorted(required)
                if seen[event] != {"refused"}
            ]
    assert wrong == [], "\n".join(wrong)


def test_every_entry_accepts_its_own_arguments() -> None:
    """The unaltered call of each entry is not refused.

    Without it a table entry that is broken refuses every variant, and
    the sweep reads that as a check working.
    """
    assert [
        name for name, call, args, kwargs in SWEPT if refused(call, args, kwargs)
    ] == []


def test_no_module_calls_a_check_through_its_module() -> None:
    """The four checks are bound by name, which is how the sweep wraps them.

    A call written `_scalar.octets(...)` would be neither listed nor
    recorded.
    """
    spelled = [
        module.__name__
        for module in mainline()
        if re.search(
            r"_scalar\.(octets|scalar|entropy|optional_entropy)\(",
            inspect.getsource(module),
        )
    ]
    assert spelled == []


def test_the_sweep_is_whole() -> None:
    """Every entry point of `musig` is swept, or excused.

    `tests/bytes_like_test.py`'s own check holds the other modules to
    their table. The classes are held by their methods, the ones that
    take bytes being driven and the rest excused.
    """
    swept = {name for name, *_ in MUSIG_CALLS} | MUSIG_NOT_SWEPT
    at_boundary = set()
    for name, member in vars(musig).items():
        if getattr(member, "__module__", "") != musig.__name__ or not at_the_boundary(
            name
        ):
            continue
        at_boundary.add(f"musig.{name}")
        if inspect.isclass(member):
            at_boundary |= {
                f"musig.{name}.{method}"
                for method, function in vars(member).items()
                if inspect.isfunction(function) and at_the_boundary(method)
            }

    assert at_boundary - swept == set()
    # and the sweep names nothing the module does not have
    assert swept - at_boundary == set()
