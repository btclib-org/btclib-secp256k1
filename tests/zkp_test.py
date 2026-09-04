# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests of btclib_secp256k1.zkp: the subpackage, its loader, its context.

The subpackage always exists and the extension it wraps does not, this
build carrying no BTCLIB_LIBSECP256K1_ZKP: `_btclib_secp256k1_zkp` is not
merely unbuilt but unimportable here, which is what makes the failure
branch of the loader (and of the context this subpackage holds) the one
this suite drives for real, and the success branch the one that needs a
stand-in -- exactly the shape `tests/extension_test.py` already uses for
`_load_lib`.

`STAND_IN` is that stand-in: the primary package's own already-resolved
`ffi` and `lib`, always there and real. `btclib_secp256k1.lib` rather
than `_btclib_secp256k1.lib` is what makes it correct under either
linkage this suite runs against -- the raw extension module carries
`lib` only on a static build (`Secp256k1ZkpCFFIExtension`'s own build is
always that shape, so `_load_lib`'s trivial `module.lib` is what a
stand-in needs), where a dynamic run resolves it through `ffi.dlopen`
instead, and `btclib_secp256k1.lib` already carries whichever answer is
true of this build. Built from a header shared closely enough with
secp256k1-zkp's own (context creation, both callbacks, randomization)
that what it drives is the real calls rather than a mock of their shape.

Every test that drives the success branch caches something into
`btclib_secp256k1.zkp`'s or `btclib_secp256k1.zkp.context`'s own module
namespace -- the same `globals()` write `__getattr__` makes in
production. That state has to be gone by the time the next test runs, in
whichever order pytest-randomly picks, so each such test restores it
itself: `monkeypatch` where the write went through it, an explicit
`delattr` in a `finally` where `__getattr__`'s own code made the write
instead.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

import btclib_secp256k1
import btclib_secp256k1.zkp.context as zkp_context
from btclib_secp256k1 import zkp

STAND_IN = types.SimpleNamespace(ffi=btclib_secp256k1.ffi, lib=btclib_secp256k1.lib)


def test_importing_the_subpackage_does_not_reach_the_extension() -> None:
    """`import btclib_secp256k1.zkp` (and `.context`) never imports it.

    `_btclib_secp256k1_zkp` is not built in this environment, so an
    eager import anywhere in the module bodies above would already have
    failed the collection of this very file. What this adds is the
    positive statement, that the extension's own name is nowhere in
    `sys.modules` -- the same check `tests/extension_test.py` runs for
    the primary package's own deferred imports.
    """
    assert "_btclib_secp256k1_zkp" not in sys.modules


def test_no_such_attribute() -> None:
    """A name the subpackage does not have is still an `AttributeError`.

    Reaches neither `_import_extension` nor the module's own globals:
    `__getattr__` raises before either, which is what keeps this test
    free of the cleanup every test below that does reach them needs.
    """
    with pytest.raises(AttributeError, match="no attribute 'nonesuch'"):
        _ = zkp.nonesuch  # type: ignore[attr-defined]


def test_attribute_access_without_the_extension_raises_import_error() -> None:
    """`zkp.ffi` (and `.lib`) explain how to get the extension, unbuilt.

    Driven for real: this build carries no `BTCLIB_LIBSECP256K1_ZKP`, so
    `importlib.import_module` genuinely fails, and what is checked is
    that the message substituted for the bare "No module named" names
    the flag and the sdist, chained from the original failure rather
    than discarding why it happened.
    """
    with pytest.raises(ImportError, match="BTCLIB_LIBSECP256K1_ZKP=1") as exc_info:
        _ = zkp.ffi
    assert isinstance(exc_info.value.__cause__, ImportError)

    with pytest.raises(ImportError, match="BTCLIB_LIBSECP256K1_ZKP=1"):
        _ = zkp.lib


def test_import_extension_with_a_stand_in() -> None:
    """`_import_extension`'s success branch, driven with a stand-in.

    The only way to reach it from a build that has no
    `_btclib_secp256k1_zkp` at all. Calling `_import_extension` directly
    touches no module global, so this test needs no cleanup.
    """
    sentinel = object()

    def importer(name: str) -> object:
        assert name == "_btclib_secp256k1_zkp"
        return sentinel

    assert zkp._import_extension(importer) is sentinel


def test_import_extension_failure_is_chained() -> None:
    """A failing `importer` is what the raised `ImportError` is chained to."""
    original = ImportError("no such module")

    def importer(name: str) -> object:  # noqa: ARG001
        raise original

    with pytest.raises(ImportError, match="BTCLIB_LIBSECP256K1_ZKP=1") as exc_info:
        zkp._import_extension(importer)
    assert exc_info.value.__cause__ is original


def test_load_lib() -> None:
    """`_load_lib` returns the `lib` of whatever module it is handed.

    One branch, `Secp256k1ZkpCFFIExtension` being static-only, so a
    stand-in with a bare `lib` attribute is the whole of what there is
    to drive.
    """
    stand_in = types.SimpleNamespace(lib=object())
    assert zkp._load_lib(stand_in) is stand_in.lib


def test_getattr_builds_and_caches_ffi_and_lib(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The glue: `_import_extension` is called once, `ffi`/`lib` cached."""
    calls: list[str] = []

    def fake_import_extension() -> Any:
        calls.append("called")
        return STAND_IN

    monkeypatch.setattr(zkp, "_import_extension", fake_import_extension)
    try:
        assert zkp.ffi is STAND_IN.ffi
        assert zkp.lib is STAND_IN.lib
        # the second read of either does not call the loader again: both
        # are now plain attributes, found before __getattr__ is ever
        # asked
        assert zkp.ffi is STAND_IN.ffi
        assert calls == ["called"]
    finally:
        delattr(zkp, "ffi")
        delattr(zkp, "lib")


def test_context_no_such_attribute() -> None:
    """The same contract, one module over."""
    with pytest.raises(AttributeError, match="no attribute 'nonesuch'"):
        _ = zkp_context.nonesuch  # type: ignore[attr-defined]


def test_ctx_without_the_extension_raises_import_error() -> None:
    """Reading `ctx` needs `btclib_secp256k1.zkp`'s own `ffi` and `lib`.

    Unbuilt here, so the `ImportError` `zkp.__getattr__` raises
    propagates through this module's own deferred `from . import ffi,
    lib` unchanged -- there is no context to build without them.
    """
    with pytest.raises(ImportError, match="BTCLIB_LIBSECP256K1_ZKP=1"):
        _ = zkp_context.ctx


def test_getattr_builds_a_real_context_with_a_stand_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`ctx` built from a stand-in extension is a real, working context.

    `STAND_IN`'s own `ffi`/`lib` stand in for the flagged extension's:
    context creation, both callback registrations and the randomization
    call are the same call on either library, so this drives the real
    calls rather than a mock of their shape.
    """
    monkeypatch.setattr(zkp, "_import_extension", lambda: STAND_IN)
    try:
        ctx = zkp_context.ctx
        assert ctx is not None
        # cached: a second read is a plain attribute, __getattr__ never
        # asked again
        assert zkp_context.ctx is ctx
    finally:
        delattr(zkp_context, "ctx")
        # ffi and lib have a real module-level default of None, unlike
        # ctx: restore it rather than delete, or a bare `ffi` reference
        # inside _record_illegal/_record_error would be unbound instead
        # of None on whatever test runs next
        zkp_context.ffi = None
        zkp_context.lib = None
        delattr(zkp_context, "_illegal_callback")
        delattr(zkp_context, "_error_callback")
        # the deferred `from . import ffi, lib` above is also the first
        # access btclib_secp256k1.zkp itself ever sees in this test, so
        # it cached its own ffi/lib the same way -- that cache is this
        # test's to undo too, not only zkp_context's own
        delattr(zkp, "ffi")
        delattr(zkp, "lib")


def test_check_with_nothing_reported() -> None:
    """With nothing reported, check returns: that is the whole behaviour."""
    zkp_context.check()


def test_illegal_argument_is_recorded_and_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Driven through the stand-in's own `lib`, a pubkey parse into nowhere.

    The same shape `tests/callbacks_test.py`'s `test_illegal_argument`
    drives for the primary context: secp256k1's `ARG_CHECK` reports a
    NULL destination through the illegal callback before it is ever
    dereferenced, and `zkp_context.check()` -- not `context.check()` --
    is what has to see it, on this module's own thread-local.
    """
    monkeypatch.setattr(zkp, "_import_extension", lambda: STAND_IN)
    try:
        ctx = zkp_context.ctx
        ffi = zkp_context.ffi
        lib = zkp_context.lib
        nowhere_args = (ffi.NULL, b"\x02" + b"\x01" * 32, 33)

        assert not lib.secp256k1_ec_pubkey_parse(ctx, *nowhere_args)
        with pytest.raises(ValueError, match="illegal argument: pubkey != NULL"):
            zkp_context.check()
        # cleared: a second call reports nothing
        zkp_context.check()
    finally:
        delattr(zkp_context, "ctx")
        # ffi and lib have a real module-level default of None, unlike
        # ctx: restore it rather than delete, or a bare `ffi` reference
        # inside _record_illegal/_record_error would be unbound instead
        # of None on whatever test runs next
        zkp_context.ffi = None
        zkp_context.lib = None
        delattr(zkp_context, "_illegal_callback")
        delattr(zkp_context, "_error_callback")
        # the deferred `from . import ffi, lib` above is also the first
        # access btclib_secp256k1.zkp itself ever sees in this test, so
        # it cached its own ffi/lib the same way -- that cache is this
        # test's to undo too, not only zkp_context's own
        delattr(zkp, "ffi")
        delattr(zkp, "lib")


def test_internal_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """An internal error reaches the caller as `RuntimeError`.

    `_record_error` is called directly, that callback being how
    secp256k1-zkp reports what it holds to be unreachable: there is no
    argument that provokes it. Only `ffi` is needed to build the
    message, so this test sets it alone rather than building a context.
    """
    monkeypatch.setattr(zkp_context, "ffi", STAND_IN.ffi, raising=False)
    zkp_context._record_error(
        STAND_IN.ffi.new("char[]", b"deliberate"), STAND_IN.ffi.NULL
    )
    with pytest.raises(RuntimeError, match="internal error: deliberate"):
        zkp_context.check()


def test_internal_error_comes_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """With both reported, the internal error is the one raised.

    A broken invariant and a caller's mistake are not the same news, and
    the first is what has to be told. Both are cleared, so neither
    lingers to be raised by an unrelated call.
    """
    monkeypatch.setattr(zkp_context, "ffi", STAND_IN.ffi, raising=False)
    zkp_context._record_illegal(
        STAND_IN.ffi.new("char[]", b"argument"), STAND_IN.ffi.NULL
    )
    zkp_context._record_error(
        STAND_IN.ffi.new("char[]", b"invariant"), STAND_IN.ffi.NULL
    )
    with pytest.raises(RuntimeError, match="invariant"):
        zkp_context.check()
    zkp_context.check()
