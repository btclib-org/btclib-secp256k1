# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Type stub for the cffi generated secp256k1-zkp extension module.

`_btclib_secp256k1.pyi`'s own module docstring has the reasoning for a
cffi extension needing a stub at all, and it holds unchanged for this
one: the extension exists only after a build, `mypy_path` in
pyproject.toml is what makes either stub reachable, and `lib` stays
`Any` for the same reason there -- secp256k1-zkp's own entry points,
declared in C and generated at build time by
`Secp256k1ZkpCFFIExtension`, would otherwise need a second hand-written
copy nothing keeps honest.

This module exists only under `BTCLIB_LIBSECP256K1_ZKP=true`
(btclib-org/btclib-secp256k1#605), which is a property of the build and
not of the interpreter checking it: mypy reads every stub `mypy_path`
names regardless of which extension the tree it is run against actually
built, so `import _btclib_secp256k1_zkp` type-checks here whether or not
this stub's own module exists on disk today.

`ffi` repeats `_FFI` from `_btclib_secp256k1.pyi` rather than importing
it: two extensions built from two independent cffi `FFI()` instances
(`scripts/cffi_build.py`'s `ffi_ext` and `ffi_ext_zkp`) hand back two
unrelated cffi module objects, each with its own `ffi` and `lib`, and
mypy resolving one from the other's stub would say something neither
extension's own build makes true.
"""

from typing import Any

class _CType:
    kind: str
    cname: str
    item: _CType

class _FFI:
    NULL: Any
    def new(self, cdecl: str | _CType, init: Any = ...) -> Any: ...
    def typeof(self, cdecl_or_cdata: Any) -> _CType: ...
    def addressof(self, cdata: Any, field: str) -> Any: ...
    def sizeof(self, cdecl_or_cdata: Any) -> int: ...
    def buffer(self, cdata: Any, size: int = ...) -> memoryview: ...
    def from_buffer(self, cdecl: str | _CType, python_buffer: Any) -> Any: ...
    def memmove(self, dest: Any, src: Any, n: int) -> None: ...
    def unpack(self, cdata: Any, length: int) -> bytes: ...
    def string(self, cdata: Any) -> bytes: ...
    def callback(self, cdecl: str, python_callable: Any) -> Any: ...
    def dlopen(self, name: str) -> Any: ...

ffi: _FFI
lib: Any
