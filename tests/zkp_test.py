# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests of btclib_secp256k1.zkp: the subpackage, its loader, its context.

The subpackage always exists and the extension it wraps exists only
where `BTCLIB_LIBSECP256K1_ZKP=true` built it, so this file meets both
builds and assumes neither. `without_the_extension` below is what makes
the state a wheel without that extension is in -- the import failing,
and nothing cached from an earlier read -- and every test that drives
either branch of the loader takes it. Reading the build's own answer
instead leaves each such test red under whichever build it did not
expect. Declaring the build would answer that instead, and this tree
declares one with a `pytest.importorskip("_btclib_secp256k1_zkp")` at
the top of the module and a `pytest.mark.zkp` beside it for the flagged
runs' own `-m zkp`: that skips the file wherever the extension is
absent, which is every build a published wheel carries, and leaves the
loader's failure branch driven only where it is present.

`STAND_IN` is the stand-in the success branch needs: the primary
package's own already-resolved `ffi` and `lib`, always there and real.
`btclib_secp256k1.lib` rather than `_btclib_secp256k1.lib` is what makes
it correct under either linkage this suite runs against -- the raw
extension module carries `lib` only on a static build
(`Secp256k1ZkpCFFIExtension`'s own build is always that shape, so
`_load_lib`'s trivial `module.lib` is what a stand-in needs), where a
dynamic run resolves it through `ffi.dlopen` instead, and
`btclib_secp256k1.lib` already carries whichever answer is true of this
build. Built from a header shared closely enough with secp256k1-zkp's
own (context creation, both callbacks, randomization) that what it
drives is the real calls rather than a mock of their shape.
"""

from __future__ import annotations

import subprocess
import sys
import types
from typing import TYPE_CHECKING, Any

import pytest

import btclib_secp256k1
import btclib_secp256k1.zkp.context as zkp_context
from btclib_secp256k1 import zkp

if TYPE_CHECKING:
    from collections.abc import Iterator

STAND_IN = types.SimpleNamespace(ffi=btclib_secp256k1.ffi, lib=btclib_secp256k1.lib)

_UNSET = object()

# what the two `__getattr__`s write into their own module globals on
# first access, each beside what it is worth before any of them has run:
# `btclib_secp256k1.zkp.context` declares `ffi` and `lib` at module scope
# with a default of None, and every other name here exists only once
# something has read one of them
_DEFERRED: tuple[tuple[Any, str, Any], ...] = (
    (zkp, "ffi", _UNSET),
    (zkp, "lib", _UNSET),
    (zkp_context, "ffi", None),
    (zkp_context, "lib", None),
    (zkp_context, "ctx", _UNSET),
    (zkp_context, "_illegal_callback", _UNSET),
    (zkp_context, "_error_callback", _UNSET),
)


def _put_back(module: Any, name: str, value: Any) -> None:
    """Give `name` the value handed in, `_UNSET` meaning it has none.

    Args:
        module: the module whose namespace is written.
        name: the attribute to write.
        value: what to write, or `_UNSET` to leave the name absent.
    """
    if value is _UNSET:
        vars(module).pop(name, None)
    else:
        setattr(module, name, value)


@pytest.fixture
def without_the_extension(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Put both modules in the state a build with no extension is in.

    Two halves, and a flagged build needs both. A `None` entry in
    `sys.modules` is the import system's own negative cache, so
    `importlib.import_module` raises `ModuleNotFoundError` out of it and
    `_import_extension` chains a real import failure -- where a stand-in
    importer would hand the wrapper back only what the wrapper gave it.
    And `_DEFERRED` is emptied, because a read that finds one of those
    names already cached never calls the `__getattr__` under test at
    all: the tests of the modules wrapping zkp-only entry points fill
    them for real under a flagged build, and pytest-randomly decides
    whether they run first.

    Written through `vars(module)` rather than through
    `monkeypatch.delattr`, which asks `hasattr` first: `hasattr(zkp,
    "ffi")` calls that same `__getattr__` and propagates its
    `ImportError` instead of answering False.

    Args:
        monkeypatch: what the `sys.modules` entry is set and unset
            through.

    Yields:
        Nothing: this fixture is the state it leaves behind it, put
        back as it was afterwards.
    """
    monkeypatch.setitem(sys.modules, "_btclib_secp256k1_zkp", None)
    saved = [
        (module, name, vars(module).get(name, _UNSET)) for module, name, _ in _DEFERRED
    ]
    for module, name, unloaded in _DEFERRED:
        _put_back(module, name, unloaded)
    try:
        yield
    finally:
        for module, name, value in saved:
            _put_back(module, name, value)


def _imported_modules(name: str) -> set[str]:
    """Return what importing that module leaves in `sys.modules`.

    A subprocess, `tests/extension_test.py`'s own `_imported_modules`
    one package down, and for a second reason beside that file's: the
    interpreter running this suite may have read `zkp.ffi` for real in
    an earlier test, and `_btclib_secp256k1_zkp` stays in its
    `sys.modules` once anything has.

    Args:
        name: the module to import in that interpreter.

    Returns:
        The names in `sys.modules` afterwards.
    """
    code = f"import sys, {name}; print('\\n'.join(sys.modules))"
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    return set(completed.stdout.split())


def test_importing_the_subpackage_does_not_reach_the_extension() -> None:
    """`import btclib_secp256k1.zkp` (and `.context`) never imports it.

    The claim is about what an import does, so it is asked of an
    interpreter that has done nothing else -- what this one holds is an
    answer about whatever ran before. Both modules are asked separately:
    importing the subpackage does not import `context`, and `context`
    reaches `zkp` only from inside its own `__getattr__`.
    """
    assert "_btclib_secp256k1_zkp" not in _imported_modules("btclib_secp256k1.zkp")
    assert "_btclib_secp256k1_zkp" not in _imported_modules(
        "btclib_secp256k1.zkp.context"
    )


def test_no_such_attribute() -> None:
    """A name the subpackage does not have is still an `AttributeError`.

    Reaches neither `_import_extension` nor the module's own globals:
    `__getattr__` raises before either, which is what keeps this test
    free of the fixture every test below that does reach them takes.
    """
    with pytest.raises(AttributeError, match="no attribute 'nonesuch'"):
        _ = zkp.nonesuch  # type: ignore[attr-defined]


@pytest.mark.usefixtures("without_the_extension")
def test_attribute_access_without_the_extension_raises_import_error() -> None:
    """`zkp.ffi` (and `.lib`) explain how to get the extension, absent.

    Driven through the real `_import_extension` and the real
    `importlib.import_module`, so what is checked is that the message
    substituted for the import system's own names the flag and the
    sdist, chained from the original failure rather than discarding why
    it happened. Neither read caches anything, `__getattr__` raising
    before it writes, so the second is the first over again.
    """
    with pytest.raises(ImportError, match="BTCLIB_LIBSECP256K1_ZKP=true") as exc_info:
        _ = zkp.ffi
    assert isinstance(exc_info.value.__cause__, ImportError)

    with pytest.raises(ImportError, match="BTCLIB_LIBSECP256K1_ZKP=true"):
        _ = zkp.lib


def test_import_extension_with_a_stand_in() -> None:
    """`_import_extension`'s success branch, driven with a stand-in.

    Calling `_import_extension` directly touches no module global, and
    the importer handed in is what decides the branch, so this test
    needs neither the fixture nor any cleanup.
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

    with pytest.raises(ImportError, match="BTCLIB_LIBSECP256K1_ZKP=true") as exc_info:
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


@pytest.mark.usefixtures("without_the_extension")
def test_getattr_builds_and_caches_ffi_and_lib(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The glue: `_import_extension` is called once, `ffi`/`lib` cached."""
    calls: list[str] = []

    def fake_import_extension() -> Any:
        calls.append("called")
        return STAND_IN

    monkeypatch.setattr(zkp, "_import_extension", fake_import_extension)
    assert zkp.ffi is STAND_IN.ffi
    assert zkp.lib is STAND_IN.lib
    # the second read of either does not call the loader again: both
    # are now plain attributes, found before __getattr__ is ever
    # asked
    assert zkp.ffi is STAND_IN.ffi
    assert calls == ["called"]


def test_context_no_such_attribute() -> None:
    """The same contract, one module over."""
    with pytest.raises(AttributeError, match="no attribute 'nonesuch'"):
        _ = zkp_context.nonesuch  # type: ignore[attr-defined]


@pytest.mark.usefixtures("without_the_extension")
def test_ctx_without_the_extension_raises_import_error() -> None:
    """Reading `ctx` needs `btclib_secp256k1.zkp`'s own `ffi` and `lib`.

    Neither is reachable under the fixture, so the `ImportError`
    `zkp.__getattr__` raises propagates through this module's own
    deferred `from . import ffi, lib` unchanged -- there is no context
    to build without them.
    """
    with pytest.raises(ImportError, match="BTCLIB_LIBSECP256K1_ZKP=true"):
        _ = zkp_context.ctx


@pytest.mark.usefixtures("without_the_extension")
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
    ctx = zkp_context.ctx
    assert ctx is not None
    # cached: a second read is a plain attribute, __getattr__ never
    # asked again
    assert zkp_context.ctx is ctx


def test_check_with_nothing_reported() -> None:
    """With nothing reported, check returns: that is the whole behaviour.

    What is reported is a thread-local of `zkp.context`'s own, and no
    wrapper in the subpackage calls `check`: a call through zkp's `lib`
    that violates a precondition leaves its reason there for whichever
    `check` a caller makes next, the contract
    `tests/callbacks_test.py`'s module docstring states for the primary
    package. `zkp.musig.SecretNonce.partial_sign` refusing a mismatched
    private key is such a call, so the empty thread-local is state this
    test makes rather than inherits.
    """
    zkp_context._reported.illegal = None
    zkp_context._reported.error = None
    zkp_context.check()


@pytest.mark.usefixtures("without_the_extension")
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
    ctx = zkp_context.ctx
    ffi = zkp_context.ffi
    lib = zkp_context.lib
    nowhere_args = (ffi.NULL, b"\x02" + b"\x01" * 32, 33)

    assert not lib.secp256k1_ec_pubkey_parse(ctx, *nowhere_args)
    with pytest.raises(ValueError, match="illegal argument: pubkey != NULL"):
        zkp_context.check()
    # cleared: a second call reports nothing
    zkp_context.check()


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
