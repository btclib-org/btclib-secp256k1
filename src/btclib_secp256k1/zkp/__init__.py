# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""BlockstreamResearch/secp256k1-zkp, under its own namespace, marked beta.

#283 decided the namespace rather than a docstring: every entry point
this package draws from the fork rather than from mainline libsecp256k1
lives under `zkp`, so the import line itself says which library answered
-- mainline's own `musig` (BIP327) and zkp's (BIP327 plus the adaptor
extensions) build incompatible session objects, and cannot be confused
for one another once the caller has to write `zkp.musig` to reach the
second. #603 is the plan this subpackage executes, and the criterion
that promotes it into the published wheels; #606 is this subpackage
itself, its loader and its own context -- the modules it will hold
follow one at a time, #607 first, and none is exposed here yet.

**beta** is a fact about the fork this subpackage draws from, not about
the wrapping: secp256k1-zkp cuts no tagged release, so the pin has
nothing for a vendored-source review to anchor against the way
mainline's does. That belongs to the namespace once, in SECURITY.md,
rather than to every entry point beneath it or to a warning every
caller would have to filter -- `filterwarnings = ["error"]` in this
project's own `pyproject.toml` is what such a warning would turn into a
hard failure on the very first `zkp` import, here and downstream, for a
status a namespace already states for free.

**This subpackage always exists; the extension it wraps mostly does
not.** `BTCLIB_LIBSECP256K1_ZKP=true` is what `scripts/cffi_build.py`
builds `_btclib_secp256k1_zkp` under, and no published wheel sets it
(#603) -- so `import btclib_secp256k1.zkp` always succeeds, and the
first access to `ffi` or `lib` is what actually reaches for the
extension: where the build has none, the caller reads how to get one
in the `ImportError` this raises, chained from the bare "No module
named" that a plain `import _btclib_secp256k1_zkp` would have left them
with instead.

That first access is also the only place the extension is imported at
all: `ffi` and `lib` are read the way `__version__` is at the top of
the package -- a module-level `__getattr__` (PEP 562) building and
caching each on first use -- so `import btclib_secp256k1`, which never
reaches this subpackage on its own, keeps paying nothing for a second
core it may never load, and `import btclib_secp256k1.zkp` on its own
pays nothing either.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

__all__ = ["ffi", "lib"]


def _import_extension(
    importer: Callable[[str], Any] = importlib.import_module,
) -> Any:
    """Import the flagged extension, or explain how to build one.

    `importer` stands in for `importlib.import_module`, which is what
    makes both branches testable regardless of which one the build
    running the suite actually has: `_btclib_secp256k1_zkp` is compiled
    only under `BTCLIB_LIBSECP256K1_ZKP=true`, which no published wheel
    sets, so the branch that succeeds needs a stand-in in the ordinary
    gate -- the same reason `btclib_secp256k1._load_lib` takes the
    module it loads as an argument rather than reading it off the
    enclosing scope.

    Args:
        importer: what does the importing; `importlib.import_module` in
            production, a stand-in in a test.

    Returns:
        The imported extension module, or the stand-in's answer.

    Raises:
        ImportError: chained from the original failure, naming the
            build flag and the sdist rather than leaving the caller
            with the bare "No module named" of the import that failed.
    """
    try:
        return importer("_btclib_secp256k1_zkp")
    except ImportError as exc:
        msg = (
            "btclib_secp256k1.zkp needs the flagged secp256k1-zkp "
            "extension, which no published wheel carries: build it "
            "from the sdist with BTCLIB_LIBSECP256K1_ZKP=true"
        )
        raise ImportError(msg) from exc


def _load_lib(module: Any) -> Any:
    """Return the libsecp256k1-zkp handle of the imported extension.

    One branch, not the package's own two: `Secp256k1ZkpCFFIExtension`
    is static-only by decision (its own docstring in
    scripts/cffi_build.py has the reasoning -- two statically linked
    cores, RTLD_LOCAL), so the module handed in always carries `lib`,
    with no shared object to search for the way a dynamic build of the
    primary extension does. Kept as a function of its own, of the same
    shape as `btclib_secp256k1._load_lib`, so that a dynamic path for
    this extension -- were that decision ever revisited -- has one
    place to grow into rather than a call site inlined wherever this
    module is read.

    Args:
        module: the imported extension, or a stand-in for it.

    Returns:
        The object every zkp wrapper calls libsecp256k1-zkp through.
    """
    return module.lib


if TYPE_CHECKING:
    # what a type checker is told instead of the function below, for the
    # reason __init__.py's own such block gives for __version__: a
    # module with a __getattr__ is one mypy stops checking attribute
    # names on otherwise, and this is the front door of the subpackage
    ffi: Any
    lib: Any
else:

    def __getattr__(name: str) -> Any:
        """Load the extension on first access to `ffi` or `lib`.

        Both are cached into this module's own namespace on the way
        out, `__version__`'s own PEP 562 shape: the second read of
        either is a dict lookup, and `dir()` does not list either name
        until something has read one of them.

        Args:
            name: the attribute being looked up.

        Returns:
            `ffi` or `lib` of the flagged extension.

        Raises:
            AttributeError: for any other name, this being the
                fallback python calls only once the module itself has
                none.
            ImportError: see `_import_extension`.
        """
        if name not in __all__:
            msg = f"module {__name__!r} has no attribute {name!r}"
            raise AttributeError(msg)
        module = _import_extension()
        globals()["ffi"] = module.ffi
        globals()["lib"] = _load_lib(module)
        return globals()[name]
