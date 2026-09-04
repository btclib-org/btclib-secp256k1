# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for what the package exports.

Section 7 of the organization standard asks for `__all__` on every module
and package, "a module under a private name excepted as no part of that
surface", and a census walking the tree rather than listing it, "so a new
public name fails until it is exported or recorded" (#357,
btclib-org/.github#79). Eleven modules sit directly under
`btclib_secp256k1` -- `_scalar`, `_secret` and `_cdata` excepted by their
own leading underscore -- so the walk below has none of btclib's own
`tests/all_test.py` nested-package machinery: no group-or-unpublished
partition, because no module here re-exports another by name, and no
transitive descent into the eleven, for the same reason.

`zkp`, the one subpackage, is out of that walk by name rather than by the
underscore convention: `library_modules()` does not import it, and
`test_every_module_is_declared` below excludes it from the names
`iter_modules` finds. An attribute access under it can raise `ImportError`
by design (`btclib_secp256k1/zkp/__init__.py`'s own docstring), which
`test_every_exported_name_exists`'s `hasattr` calls do not tolerate --
`hasattr` swallows `AttributeError` alone. `tests/zkp_test.py` is where
the subpackage is covered instead.

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
from pathlib import Path
from pkgutil import iter_modules
from types import ModuleType

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
)

# what a module defines without a leading underscore and deliberately does
# not export, with the reason beside the list in the module's own
# docstring or comments. A name added here is a decision; a name that has
# to be added here to make the suite pass is one that was about to become
# public by accident. Empty today: nothing in this package currently
# defines a public name it withholds
UNEXPORTED: dict[str, list[str]] = {}


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
    ]


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


def defined_public_names(module: ModuleType) -> set[str]:
    """Return the public names a module defines itself.

    Everything in its namespace, minus the underscored, minus what it
    imported, minus the modules: a submodule becomes an attribute of the
    package as soon as anything imports it, so `context` is in
    `vars(btclib_secp256k1)` by the time any test runs even though this
    module never names it.
    """
    imported = imported_names(module)
    return {
        name
        for name, value in vars(module).items()
        if public_name(name)
        and name not in imported
        and not isinstance(value, ModuleType)
    }


def test_every_exported_name_exists() -> None:
    """An `__all__` entry that names nothing is a broken `import *`."""
    for module in library_modules():
        names = getattr(module, "__all__", None)
        assert names is not None, f"{module.__name__} declares no __all__"
        assert names, f"{module.__name__} declares an empty __all__"
        for name in names:
            assert hasattr(module, name), f"{module.__name__}.{name} is not there"


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

    `zkp` is excluded by name rather than left to fail this comparison:
    the module docstring above has the reason it carries none of the
    checks this file runs, and `tests/zkp_test.py` is where it is
    declared instead.
    """
    found = sorted(
        name
        for _, name, _ in iter_modules(btclib_secp256k1.__path__)
        if public_name(name) and name != "zkp"
    )
    declared = sorted(
        module.__name__.rsplit(".", 1)[-1] for module in library_modules()[1:]
    )
    assert found == declared, (
        f"btclib_secp256k1/ holds {found}, this file names {declared}"
    )
