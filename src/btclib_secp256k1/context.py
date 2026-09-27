# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Shared libsecp256k1 context, and what its illegal callback reports."""

from __future__ import annotations

import secrets
import threading

from . import CData, ffi, lib

# `ctx` is exported for the caller reaching `lib` directly, as the
# README's "Wrapped modules" section shows: `secp256k1_musig_partial_sign`
# and every other raw call this package makes needs the context passed
# in. `_randomize` stays unexported despite the same README naming it --
# private is its own answer to who may call it again, not a name this
# list withholds
__all__ = ["check", "ctx"]

# 1 is SECP256K1_CONTEXT_NONE: since libsecp256k1 0.2 signing and
# verification work with any context, and the SIGN/VERIFY flags are
# deprecated
ctx = lib.secp256k1_context_create(1)


class _Reported(threading.local):
    """What libsecp256k1 last reported on the calling thread.

    A callback runs on the thread of the call that triggered it, so a
    thread local is what attributes a message to the right call.

    Attributes:
        illegal: the last violated precondition, or None.
    """

    illegal: str | None = None


_reported = _Reported()


def _record_illegal(message: CData, data: CData) -> None:  # noqa: ARG001
    """Record a violated precondition. Called by libsecp256k1.

    `data` is unused: the signature is the C callback's, fixed by
    libsecp256k1's own type, not this function's to shorten.

    Args:
        message: the failed condition, as a C string.
        data: the pointer the callback was registered with, NULL here.
    """
    _reported.illegal = ffi.string(message).decode()


# libsecp256k1 reports a violated precondition (an illegal argument, an
# object in an invalid state) through the illegal callback, then returns
# 0. Its abort()ing default is replaced, in the vendored build, by a
# stub that does nothing: that keeps an illegal argument from taking the
# hosting process down, but leaves the caller with a bare 0 and no reason
# for it. On the shared context the callback instead records what was
# reported, so that check() can raise it. The reference to the cffi
# callback has to outlive the context, hence the module level name.
#
# An internal error is different news: it means the library itself
# cannot be trusted -- hardware failure, miscompilation, memory
# corruption -- and upstream's own header says anything may happen once
# the callback reporting it returns. No callback is set for it here, so
# the vendored build's own aborting default applies, and this context
# never gets the chance to return a value -- still less to sign -- after
# libsecp256k1 has told it not to trust itself. See SECURITY.md for the
# split.
_illegal_callback = ffi.callback("void(*)(const char *, void *)", _record_illegal)
lib.secp256k1_context_set_illegal_callback(ctx, _illegal_callback, ffi.NULL)


def _randomize(context: CData) -> None:
    """Re-blind the signing precomputation of that context.

    Protects against side-channel leakage, as libsecp256k1 recommends,
    and is called below on the shared context at import time.

    Repeating it is a caller's to do and needs exclusive access to the
    context: this is one of the few libsecp256k1 calls that mutates one,
    and the header says to randomize at creation time -- which is what
    happens below -- or to hold a read-write lock. Everything else in
    these bindings is safe to call from several threads *because* the
    shared context is randomized once, before any of them exists, so a
    second call on `ctx` while another thread is signing takes that
    guarantee away. See the Thread safety section of the README.

    The context is an argument rather than the module-level `ctx` for
    the same reason `_load_lib` takes the module: a line called once, at
    import, is a line no test can reach afterwards -- and what is worth
    reaching here is the 32, an entropy requirement of
    secp256k1_context_randomize that no answer this package returns
    would reveal if it were wrong.

    Args:
        context: the libsecp256k1 context to re-blind.

    Raises:
        RuntimeError: if libsecp256k1 refuses the context -- the static
            one, which it will not randomize -- or fails for any other
            reason, which a 32-octet seed cannot make it do.
    """
    if not lib.secp256k1_context_randomize(context, secrets.token_bytes(32)):
        msg = "libsecp256k1 context randomization failed"
        raise RuntimeError(msg)


_randomize(ctx)


def check() -> None:
    """Raise what libsecp256k1 reported on this thread, if anything.

    The message is the failed precondition itself, as libsecp256k1
    stringifies the condition of its own check: signing twice with the
    same MuSig2 secret nonce, for one, is reported as the failed magic
    check of the nonce that the first signature zeroed.

    It is for a call made through `lib` directly, as a MuSig2 session
    is, and it is the caller's to make: no wrapper in this package calls
    it, so what it reports is whatever was recorded last on this thread
    by anything at all. Call it immediately after the call whose return
    value you are explaining, and read nothing into a message from any
    other one.

    A wrapper is one of those others. Handed an object libsecp256k1
    cannot read, a wrapper answers its own verdict -- `False` from a
    verification, `None` from a sum, its own `ValueError` where a return
    code let it raise -- and the reason is recorded here on the way past.
    So a message on the thread may be a wrapper's rather than the
    caller's, which is the whole of why this asks to be called at once.

    What was recorded is cleared, so a second call reports nothing and
    a later one cannot inherit this call's message.

    Raises:
        ValueError: if libsecp256k1 reported a violated precondition.
    """
    illegal = _reported.illegal
    _reported.illegal = None
    if illegal is not None:
        raise ValueError(f"libsecp256k1 illegal argument: {illegal}")
