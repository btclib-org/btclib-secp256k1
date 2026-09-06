# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""zkp's own libsecp256k1 context, and what it reports through it.

Mirrors `btclib_secp256k1.context`, one library over: two statically
linked cores share nothing at run time, which is what makes this
necessary rather than a convenience. `context.py`'s own docstring has
the reasoning `ctx` and `check` repeat here -- a shared context,
randomized once at creation, and a thread-local pair of callbacks that
`check` raises what was last reported through. A call made through
zkp's `lib` is explained by zkp's `check`, never by the primary
package's: two libraries reporting into one thread-local would
attribute one library's message to a call the other library made.

Building either needs the extension `btclib_secp256k1.zkp` loads on
first access to `ffi` or `lib`, so `ctx` is read the same lazy way here:
a module-level `__getattr__` builds it, and the context, on first
access, rather than at import of this module. That keeps
`import btclib_secp256k1.zkp.context` on its own safe without the flag
-- which is what lets docs/source/btclib_secp256k1.rst document this
module's own docstring, the documentation build never setting
`BTCLIB_LIBSECP256K1_ZKP`.

`_bindings` below is the one place every module wrapping a zkp-only
entry point (#607 onward) reaches for `ffi`, `lib` and `ctx` together:
each such module defers the three to its own first call rather than to
its own top level, for the reason this module's `__getattr__` already
states for `ctx` alone, and `_bindings` is that deferral made once,
here, instead of once per module. Called through `context._bindings()`
rather than copied, so that a fifth wrapper module takes on no ordering
requirement of its own -- reading `ctx` first, as this module's
`__getattr__` already does, is what makes `ffi` and `lib` real, and a
caller of `_bindings` never reads either before that has happened.

Deferred to the first call is also what the primary package's own
`context.py` is not: that one builds at plain module scope, which
Python's own import lock serializes -- every thread importing it blocks
on the same lock, and one of them runs the module body while the rest
wait for the result already sitting in `sys.modules`. Nothing here
imports the extension at module scope, by decision, so nothing plays
that part for `_load` below: two threads whose first touch of `ctx`
overlaps both pass its `"ctx" not in globals()` check before either has
written anything, and both build a context, `README.md`'s Thread safety
section's own guarantee -- "it runs once before any thread exists" --
holding only of the sequential path (#717). `_lock` is what `_load`
takes instead, held for the whole build and rechecked once acquired: a
thread that waited for it finds `ctx` already there and returns that
one, never a second context built to be discarded.
"""

from __future__ import annotations

import secrets
import threading
from typing import TYPE_CHECKING, Any

from btclib_secp256k1 import CData

__all__ = ["check", "ctx"]


class _Reported(threading.local):
    """What secp256k1-zkp last reported on the calling thread.

    The same shape as `btclib_secp256k1.context._Reported`, on a thread
    local of its own: a callback runs on the thread of the call that
    triggered it, and this is a different pair of callbacks reporting
    from a different context.

    Attributes:
        illegal: the last violated precondition, or None.
        error: the last internal error, or None.
    """

    illegal: str | None = None
    error: str | None = None


_reported = _Reported()

# guards the build `_load` below runs: held for the whole of it, and
# rechecked once acquired, so that two threads racing the first call
# build the context once between them rather than one each (#717)
_lock = threading.Lock()

# real, unconditional bindings -- unlike `ctx` below, `ffi` and `lib` are
# read as bare globals inside the callbacks and `_randomize`, so ruff's
# own undefined-name check needs an assignment here rather than the
# annotation-only declaration `ctx` gets under TYPE_CHECKING. `None`
# until the `__getattr__` below overwrites both with the real thing, on
# the first access that needs either -- always before secp256k1-zkp can
# call back into `_record_illegal` or `_record_error`, nothing reaching
# either until the context this module builds has had them registered
# on it
ffi: Any = None
lib: Any = None


def _record_illegal(message: CData, data: CData) -> None:  # noqa: ARG001
    """Record a violated precondition. Called by secp256k1-zkp.

    Args:
        message: the failed condition, as a C string.
        data: the pointer the callback was registered with, NULL here.
    """
    _reported.illegal = ffi.string(message).decode()


def _record_error(message: CData, data: CData) -> None:  # noqa: ARG001
    """Record an internal error. Called by secp256k1-zkp.

    Args:
        message: the failed condition, as a C string.
        data: the pointer the callback was registered with, NULL here.
    """
    _reported.error = ffi.string(message).decode()


def _randomize(context: CData) -> None:
    """Re-blind the signing precomputation of that context.

    `context.py`'s own `_randomize` has the reasoning; this is the same
    call, made once, on this module's own context rather than the
    package's.

    Args:
        context: the libsecp256k1-zkp context to re-blind.

    Raises:
        RuntimeError: if secp256k1-zkp fails, which a 32-octet seed
            cannot make it do.
    """
    if not lib.secp256k1_context_randomize(context, secrets.token_bytes(32)):
        raise RuntimeError("libsecp256k1-zkp context randomization failed")


def check() -> None:
    """Raise what secp256k1-zkp reported on this thread, if anything.

    `context.check`'s own docstring has the contract this repeats: call
    it immediately after the call through zkp's `lib` whose return value
    you are explaining, and read nothing into a message from any other
    one. What was recorded is cleared, so a second call reports nothing.

    Raises:
        ValueError: if secp256k1-zkp reported a violated precondition.
        RuntimeError: if it reported an internal error, which takes
            precedence, being the graver of the two.
    """
    illegal, error = _reported.illegal, _reported.error
    _reported.illegal = _reported.error = None
    if error is not None:
        raise RuntimeError(f"libsecp256k1-zkp internal error: {error}")
    if illegal is not None:
        raise ValueError(f"libsecp256k1-zkp illegal argument: {illegal}")


def _load(name: str) -> Any:
    """Build this module's context on first access to `ctx`.

    `__getattr__` below is this under the one name Python calls on its
    own; `_bindings` calls it under this one instead, an ordinary
    function unlike the dunder, so that a type checker -- which treats
    `if TYPE_CHECKING:` as taken and so never sees a name `__getattr__`
    only the `else` branch below binds -- has one to check `_bindings`'
    own call against.

    Imports `btclib_secp256k1.zkp` here, deferred rather than at
    module scope, so that importing this module never reaches for
    the extension on its own -- only reading `ctx` does, which the
    modules wrapping zkp-only entry points (#607 onward) do inside
    each call rather than at their own import. `_lock` is what makes
    that deferral safe under several threads (#717): held for the
    whole build, and the module docstring has the reasoning for why
    that is needed here and not in the primary package's own
    `context.py`, which builds at module scope instead.

    Args:
        name: the attribute being looked up.

    Returns:
        The context, for `ctx`.

    Raises:
        AttributeError: for any other name.
        ImportError: from `btclib_secp256k1.zkp`, if the extension
            this needs was never built.
    """
    if name != "ctx":
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    with _lock:
        if "ctx" in globals():
            # lost the race for the lock, not the build: whichever
            # thread got there first already wrote every name below
            return globals()["ctx"]
        from . import ffi, lib  # noqa: PLC0415

        globals()["ffi"] = ffi
        globals()["lib"] = lib

        # the reference to each cffi callback has to outlive the
        # context, hence the module-level names: context.py's own such
        # comment has the reasoning, unchanged here
        illegal_callback = ffi.callback(
            "void(*)(const char *, void *)", _record_illegal
        )
        error_callback = ffi.callback("void(*)(const char *, void *)", _record_error)
        globals()["_illegal_callback"] = illegal_callback
        globals()["_error_callback"] = error_callback

        context = lib.secp256k1_context_create(1)
        lib.secp256k1_context_set_illegal_callback(context, illegal_callback, ffi.NULL)
        lib.secp256k1_context_set_error_callback(context, error_callback, ffi.NULL)
        _randomize(context)

        # the last of the five globals this builds, written after
        # `ffi`, `lib` and both closures rather than beside them:
        # `_bindings` reads `ctx` alone, taking no lock, to decide the
        # other four are there, so it is this assignment's position
        # that makes that read safe (#717)
        globals()["ctx"] = context
        return context


def _bindings() -> tuple[Any, Any, CData]:
    """Return this module's `ffi`, `lib` and `ctx` together, building once.

    Every module wrapping a zkp-only entry point calls this rather than
    reading `ffi`, `lib` or `ctx` on its own. `context.ctx` -- an
    ordinary attribute access -- calls `_load` only the first time,
    Python's own attribute protocol finding `ctx` already in this
    module's globals on every read after that; calling `_load`
    unconditionally here would skip that check and rebuild a fresh
    context, with fresh callback closures, on every call -- leaving
    whichever earlier context a caller is still holding registered
    against closures nothing references any more, freed under it. This
    checks the same globals `_load` writes into before calling it,
    which is what makes a call here answer the one context every other
    caller in the process already has, built at most once. The check
    itself takes no lock -- `_load`'s own docstring has the reasoning
    for why one call here still answers the single context two racing
    threads would otherwise each build (#717).

    Returns:
        This module's own `ffi`, `lib` and `ctx`.

    Raises:
        ImportError: from `btclib_secp256k1.zkp`, if the flagged
            extension this needs was never built.
    """
    ctx = globals()["ctx"] if "ctx" in globals() else _load("ctx")
    return ffi, lib, ctx


if TYPE_CHECKING:
    ctx: CData
else:
    __getattr__ = _load
