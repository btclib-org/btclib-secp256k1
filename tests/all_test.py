# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for what the package exports.

Section 7 of the organization standard asks for `__all__` on every module
and package, "a module under a private name excepted as no part of that
surface", and a census walking the tree rather than listing it, "so a new
public name fails until it is exported or recorded" (#357,
btclib-org/.github#79). The modules sitting directly under
`btclib_secp256k1` are all in the census -- `_scalar`, `_secret` and
`_cdata` excepted by their own leading underscore -- and the walk below
has none of btclib's own `tests/all_test.py` group-or-unpublished
partition, no module here re-exporting another by name.

`zkp` is a subpackage, and the census descends into it: what it holds
wraps secp256k1-zkp the way the modules above wrap libsecp256k1, and a
census walking the tree is what section 7 asks for. The names declared
under it that are served by loading the flagged extension -- `zkp.ffi`,
`zkp.lib` and `zkp.context.ctx`, each a module-level `__getattr__` away
(`btclib_secp256k1/zkp/__init__.py`'s own docstring) -- raise
`ImportError` without `BTCLIB_LIBSECP256K1_ZKP`, which `hasattr` does
not tolerate: it swallows `AttributeError` alone. `exported_name_exists`
below is what reads a name instead, and nothing this file imports
reaches for that extension (#627). `tests/zkp_test.py` is where the
subpackage's own behaviour is tested.

Every module's `ffi`, `lib`, `CData`, `BytesLike`, `MutableBytesLike` and
`ctx` come from `from . import ...` or `from .context import ctx`, which
is what a caller reaching past the argument-checked entry points needs --
SECURITY.md names that caller directly. That makes each of them an
import in every module except the one that defines it, so
`test_no_module_exports_a_name_it_imported` is what keeps one of them
from drifting into a second module's `__all__` by way of the same `from`
line that already binds it there.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from importlib import import_module
from pathlib import Path
from pkgutil import iter_modules
from types import ModuleType

import pytest

import btclib_secp256k1
from btclib_secp256k1 import (
    context,
    dsa,
    ecdh,
    ellswift,
    hashes,
    keys,
    musig,
    recovery,
    silentpayments,
    ssa,
    xonly,
    zkp,
)
from btclib_secp256k1.zkp import context as zkp_context
from btclib_secp256k1.zkp import ecdsa_s2c as zkp_ecdsa_s2c
from btclib_secp256k1.zkp import generator as zkp_generator
from btclib_secp256k1.zkp import musig as zkp_musig
from btclib_secp256k1.zkp import rangeproof as zkp_rangeproof

# what a module defines without a leading underscore and deliberately does
# not export, with the reason beside the list in the module's own
# docstring or comments. A name added here is a decision; a name that has
# to be added here to make the suite pass is one that was about to become
# public by accident
UNEXPORTED: dict[str, list[str]] = {
    # `ffi` and `lib` are bound to None at module level and rebound when
    # `ctx` is first read: that module's own comment has why they are
    # assignments where `ctx` is an annotation, and `btclib_secp256k1.zkp`
    # is where a caller reads either of them from
    "btclib_secp256k1.zkp.context": ["ffi", "lib"],
}


def public_name(name: str) -> bool:
    """Whether a module name is public, i.e. does not open with `_`."""
    return not name.startswith("_")


def library_modules() -> list[ModuleType]:
    """Return the package and every module under it, private ones out.

    Found rather than listed: a module added to `btclib_secp256k1/` is
    one this asks about. `_scalar`, `_secret` and `_cdata` are out, and
    so is anything else under a private name: a module whose name opens
    with an underscore is not part of the surface, so what is public
    *in* it is not reachable by any spelling a caller is offered.
    """
    return [
        btclib_secp256k1,
        context,
        dsa,
        ecdh,
        ellswift,
        hashes,
        keys,
        musig,
        recovery,
        silentpayments,
        ssa,
        xonly,
        zkp,
        zkp_context,
        zkp_ecdsa_s2c,
        zkp_generator,
        zkp_musig,
        zkp_rangeproof,
    ]


def found_modules(package: ModuleType, prefix: str = "") -> Iterator[str]:
    """Yield the public module names a package holds, subpackages descended.

    Args:
        package: the package to read.
        prefix: what the names it holds are reached through, `zkp.` for
            what the subpackage holds and empty for the package itself.

    Yields:
        Each name, as `library_modules` spells it.
    """
    for _, name, is_package in iter_modules(package.__path__):
        if not public_name(name):
            continue
        yield prefix + name
        if is_package:
            subpackage = import_module(f"{package.__name__}.{name}")
            yield from found_modules(subpackage, f"{prefix}{name}.")


def module_scope(body: Iterable[ast.stmt]) -> Iterator[ast.stmt]:
    """Yield the statements a module executes in its own namespace.

    Every statement of the body, and then inside each compound one, which
    runs at module scope too: an import in a module-level `try` or `if`
    binds a global exactly as a top-level one does. A function or a class
    opens a scope of its own, so an import in either binds nothing here,
    and neither is descended into.
    """
    for node in body:
        yield node
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        nested: list[ast.stmt] = []
        for field in ("body", "orelse", "finalbody"):
            statements = getattr(node, field, None)
            if isinstance(statements, list):
                nested += statements
        for clause in (*getattr(node, "handlers", ()), *getattr(node, "cases", ())):
            nested += clause.body
        yield from module_scope(nested)


def imported_names_in(source: str) -> set[str]:
    """Return the names the import statements of one module source bind."""
    return {
        alias.asname or alias.name.split(".")[0]
        for node in module_scope(ast.parse(source).body)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }


def imported_names(module: ModuleType) -> set[str]:
    """Return the names a module's own import statements bind.

    Read off the source rather than the module object, there being
    nothing in a module's namespace to say how a name got there.
    """
    return imported_names_in(Path(str(module.__file__)).read_text(encoding="utf-8"))


def is_own_submodule(module: ModuleType, name: str, value: object) -> bool:
    """Whether a name in a module's namespace is a submodule of it.

    Importing `btclib_secp256k1.zkp.context` binds `context` in
    `vars(btclib_secp256k1.zkp)`, so a package's namespace holds what is
    under it whether or not it names any of it, and a census of what a
    module *defines* has to leave those out. A submodule bound that way
    carries the qualified name it is reached by, which is what this
    compares against.

    Asked that way rather than with `isinstance(value, ModuleType)`,
    which a cffi `Lib` answers True to without being one: its `__mro__`
    is `Lib`, `object` and `issubclass(_cffi_backend.Lib, ModuleType)`
    is False, but it reports `module` as its `__class__`, and
    `isinstance` consults `__class__` where that differs from `type()`.
    `btclib_secp256k1.zkp.context.lib` holds such an object once the
    flagged extension has been loaded, so an `isinstance` test drops it
    from the census on a build that has that extension and keeps it on a
    build that does not -- the two answering differently about the same
    source (btclib-org/btclib-secp256k1#654).

    Args:
        module: the module whose namespace holds the name.
        name: the name it is bound under.
        value: what it is bound to.

    Returns:
        Whether it is a submodule of that module under its own name.
    """
    return getattr(value, "__name__", None) == f"{module.__name__}.{name}"


def defined_public_names(module: ModuleType) -> set[str]:
    """Return the public names a module defines itself.

    Everything in its namespace, minus the underscored, minus what it
    imported, minus its own submodules: a submodule becomes an attribute
    of the package as soon as anything imports it, so `context` is in
    `vars(btclib_secp256k1)` by the time any test runs even though this
    module never names it. `is_own_submodule` is what asks that, and its
    own docstring has why it is not an `isinstance` test.
    """
    imported = imported_names(module)
    return {
        name
        for name, value in vars(module).items()
        if public_name(name)
        and name not in imported
        and not is_own_submodule(module, name, value)
    }


def exported_name_exists(module: ModuleType, name: str) -> bool:
    """Whether a module answers one of its own `__all__` entries.

    What `hasattr` would answer, and the case it cannot be asked:
    `zkp.ffi`, `zkp.lib` and `zkp.context.ctx` are served by loading the
    flagged extension, so without `BTCLIB_LIBSECP256K1_ZKP` reading one
    raises `ImportError` rather than answering. That is a name the
    module serves -- what it wanted was the extension -- and it is told
    from a broken import by the flag the message names, which is where
    `btclib_secp256k1.zkp` sends a caller who has no such build.

    Of `btclib_secp256k1.zkp` itself this therefore asks nothing: that
    module's `__getattr__` refuses what is not in `__all__` and reaches
    for the extension for what is, so every entry of that `__all__`
    answers `ImportError` where no flagged build exists, this one
    included. `zkp.context`'s `__getattr__` names `ctx` rather than
    reading `__all__`, so an `__all__` entry it does not serve is one
    this does report. A flagged build answers those entries for real,
    and `test_every_name_the_zkp_subpackage_exports_is_served` is where
    the census gets to ask them.

    Args:
        module: the module declaring the name.
        name: one of its `__all__` entries.

    Returns:
        Whether the module answers it.
    """
    try:
        getattr(module, name)
    except AttributeError:
        return False
    except ImportError as exc:
        return "BTCLIB_LIBSECP256K1_ZKP" in str(exc)
    return True


def test_every_exported_name_exists() -> None:
    """An `__all__` entry that names nothing is a broken `import *`."""
    for module in library_modules():
        names = getattr(module, "__all__", None)
        assert names is not None, f"{module.__name__} declares no __all__"
        assert names, f"{module.__name__} declares an empty __all__"
        for name in names:
            assert exported_name_exists(module, name), (
                f"{module.__name__}.{name} is not there"
            )


def test_an_exported_name_that_is_not_there_is_reported() -> None:
    """The check above is worth what its reader does with a miss.

    Asked of the modules themselves rather than of a stand-in: a
    module-level `__getattr__` refuses an unknown name with
    `AttributeError` and reaches for the extension for a name it
    serves, and it is the real one that decides which. `dsa` is the
    ordinary shape beside them, having no `__getattr__` at all.
    """
    assert exported_name_exists(dsa, "sign")
    assert not exported_name_exists(dsa, "no_such_name")
    assert not exported_name_exists(zkp, "no_such_name")
    assert not exported_name_exists(zkp_context, "no_such_name")
    # served, whether this build can load the extension or not
    assert exported_name_exists(zkp, "ffi")


def _no_extension(name: str) -> object:
    """Fail the import the way a build without the flagged extension does.

    `btclib_secp256k1.zkp._import_extension` takes its importer as an
    argument so that either branch is drivable whichever build runs the
    suite, its own docstring giving that reason, and this is what
    `importlib.import_module` meeting no such module does.

    Args:
        name: the module `_import_extension` asks for.

    Raises:
        ModuleNotFoundError: what the import system raises for a module
            that is not there.
    """
    msg = f"No module named {name!r}"
    raise ModuleNotFoundError(msg)


def test_an_import_error_naming_the_flag_counts_as_a_name_it_serves() -> None:
    """The arm that tells a deferred extension from a broken import.

    Asked of stand-ins rather than of `btclib_secp256k1.zkp`, so that
    both answers hold under either build: a flagged build serves `ffi`
    and `lib` for real, and the arm is then unreachable through that
    module however the census is run
    (btclib-org/btclib-secp256k1#658).

    What the first stand-in raises is `_import_extension`'s own
    exception, taken from that function rather than written here from
    reading the one under test; the second stands for an import that is
    simply broken, whose message names no flag. Both serve the name
    through a module-level `__getattr__`, PEP 562 being how
    `btclib_secp256k1.zkp` serves its own.
    """
    with pytest.raises(ImportError) as caught:
        zkp._import_extension(_no_extension)

    def wants_the_extension(name: str) -> object:
        assert name == "ffi"
        raise caught.value

    def is_simply_broken(name: str) -> object:
        msg = f"cannot import name {name!r}"
        raise ImportError(msg)

    deferred = ModuleType("stand_in_for_a_build_without_the_extension")
    deferred.__dict__["__getattr__"] = wants_the_extension
    broken = ModuleType("stand_in_for_a_module_that_does_not_import")
    broken.__dict__["__getattr__"] = is_simply_broken
    assert exported_name_exists(deferred, "ffi")
    assert not exported_name_exists(broken, "ffi")


@pytest.mark.zkp
def test_every_name_the_zkp_subpackage_exports_is_served() -> None:
    """What `test_every_exported_name_exists` cannot ask of `zkp`.

    That module's `__getattr__` reaches for the flagged extension for
    every entry of its own `__all__`, so where the extension is absent
    each of them answers `ImportError` and the census counts it served
    whatever the list holds (btclib-org/btclib-secp256k1#650). Under
    the extension a read resolves or it does not, which is the question
    the census exists to ask.

    Marked and guarded the way
    `test_the_census_finds_lib_bound_to_the_real_extension` is: `-m
    zkp` is the selector of both flagged jobs in
    `.github/workflows/test.yml`, and the `importorskip` is what lets
    an unflagged run collect this file and report this test skipped
    rather than error on it.
    """
    pytest.importorskip("_btclib_secp256k1_zkp")
    for name in zkp.__all__:
        assert exported_name_exists(zkp, name), f"zkp.{name} is not there"


def test_no_module_exports_a_name_it_imported() -> None:
    """A module exports what it defines. Nothing here re-exports.

    Unlike a package's `__init__`, a module re-exporting a name is a
    leak: `ffi` reached through `btclib_secp256k1.dsa` is that module's
    import section, where `btclib_secp256k1.ffi` is the name a caller
    wants. No module in this package has a reason to re-export anything,
    so the check is unconditional -- a name here would be the first one
    to need the escape hatch btclib's own version of this test carries.
    """
    for module in library_modules():
        imported = imported_names(module)
        leaked = {name for name in module.__all__ if name in imported}
        assert not leaked, f"{module.__name__} re-exports {sorted(leaked)}"


def test_nothing_becomes_public_by_accident() -> None:
    """Every public name is exported or recorded as kept out.

    This is the check the underscore convention cannot make: a helper
    that grows into a name callers depend on does so silently, where a
    module takes an edit to `__all__`. `UNEXPORTED` is that edit, and
    `sorted` is what the failure reads as -- the names not accounted
    for, against the ones that are.
    """
    for module in library_modules():
        kept_out = sorted(defined_public_names(module) - set(module.__all__))
        assert kept_out == UNEXPORTED.get(module.__name__, []), (
            f"{module.__name__} defines public names that are neither"
            f" exported nor recorded in UNEXPORTED: {kept_out}"
        )


class _ReportsItselfAModule:
    """A stand-in for a cffi `Lib`, of the shape measured on a real one.

    `__class__` reporting `module` while `type()` reports something else
    is the whole of what makes `isinstance(lib, ModuleType)` disagree
    with `issubclass(type(lib), ModuleType)`; the qualified `__name__` is
    the other half of what `is_own_submodule` reads. Written from the
    real object's own answers rather than from the function under test,
    so what it drives is the case that arises rather than one that would
    pass.
    """

    # the suppression is the point rather than an annoyance: mypy
    # refuses this assignment because a `__class__` that disagrees with
    # `type()` is exactly what a well-behaved object does not do, which
    # is why an `isinstance` test on one is worth a stand-in
    __class__ = ModuleType  # type: ignore[assignment]
    __name__ = "_extension.lib"


def test_an_object_that_reports_itself_a_module_is_not_a_submodule() -> None:
    """`is_own_submodule` answers what a name is, not what it claims.

    The stand-in is what an `isinstance` test would drop from the
    census, and dropping it is what made this file pass under a build
    without the flagged extension and fail under one with it. Beside it,
    the two ordinary answers: a real submodule bound by import side
    effect, and a function the module defines.
    """
    assert isinstance(_ReportsItselfAModule(), ModuleType)
    assert not is_own_submodule(zkp_context, "lib", _ReportsItselfAModule())
    assert is_own_submodule(btclib_secp256k1, "zkp", zkp)
    assert not is_own_submodule(dsa, "sign", dsa.sign)


@pytest.mark.zkp
def test_the_census_finds_lib_bound_to_the_real_extension() -> None:
    """`zkp.context.lib` is a defined public name whatever it is bound to.

    The test above drives `is_own_submodule` against a stand-in of the
    shape a cffi `Lib` has, and every unflagged run collects it; this
    one drives it against the object itself, which exists only where
    `BTCLIB_LIBSECP256K1_ZKP=true` built the extension. Reading
    `zkp.context.ctx` is what binds `lib` to it, that module's own
    `__getattr__` populating `ffi` and `lib` as a side effect of
    building the context, so what the census faces here is the case
    btclib-org/btclib-secp256k1#654 was about rather than a
    reconstruction of it.

    The `isinstance` assertion is the premise rather than the claim: it
    is what an `isinstance`-based filter would act on, and a cffi that
    stopped reporting `module` as a `Lib`'s `__class__` would fail here
    and say so, instead of leaving this test passing for a reason that
    had gone away.

    Marked `zkp` and guarded with `importorskip`, which is what puts it
    in a run that exists: `-m zkp` is the selector of both flagged jobs
    in `.github/workflows/test.yml`, and the guard is what lets the
    unflagged runs collect this file and skip this one test rather than
    error on it.
    """
    pytest.importorskip("_btclib_secp256k1_zkp")
    assert zkp_context.ctx is not None
    assert isinstance(zkp_context.lib, ModuleType)
    kept_out = sorted(defined_public_names(zkp_context) - set(zkp_context.__all__))
    assert kept_out == UNEXPORTED[zkp_context.__name__]


def test_the_import_scan_reaches_a_nested_import() -> None:
    """A module-level `try` binds a global, and a function body does not.

    None of this package's own modules import inside a `try`, so nothing
    above would otherwise exercise that branch of `module_scope` -- and
    the check above is only as good as this scan: an optional import
    bound that way and named in `__all__` is exactly the re-export
    `test_no_module_exports_a_name_it_imported` refuses, and reading
    `tree.body` alone would have let it through.
    """
    source = (
        "try:\n"
        "    from dependency import PublicType\n"
        "except ImportError:\n"
        "    from fallback import PublicType\n"
        "def f():\n"
        "    import local\n"
        "class C:\n"
        "    import attribute\n"
    )
    assert imported_names_in(source) == {"PublicType"}


def test_every_module_is_declared() -> None:
    """A module added to the package directory is one this file asks about.

    `library_modules` is written out rather than discovered from
    `pkgutil`, so this is the other half: a module added under
    `btclib_secp256k1/` and not imported above would be silently absent
    from every check in this file, which a discovered list would not
    let happen.

    A module under `zkp` is named for the subpackage it sits in --
    `zkp.musig`, which is not `musig` -- so that the two cannot be
    taken for one another in the comparison or in its failure.
    """
    found = sorted(found_modules(btclib_secp256k1))
    declared = sorted(
        module.__name__.removeprefix(f"{btclib_secp256k1.__name__}.")
        for module in library_modules()[1:]
    )
    assert found == declared, (
        f"btclib_secp256k1/ holds {found}, this file names {declared}"
    )
